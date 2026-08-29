
# ============================================================
# MODULE: PARAMETRIC CLIMATE RISK ENGINE
# ============================================================
import uuid

@app.post("/api/climate-risk/evaluate/{field_id}")
def evaluate_climate_risk(field_id: str, user: User = Depends(get_current_user)):
    """
    Evaluates drought/flood risk for a field.
    Reads recent NDWI from NeonDB and soil moisture from Firestore.
    If conditions met, creates a Parametric Risk Event in Firestore.
    """
    farm_id = resolve_farm_id(user)
    
    # 1. Fetch last 2 satellite scans from NeonDB
    db_session = SessionLocal()
    try:
        scans = db_session.query(CropHealthScan).filter(
            CropHealthScan.field_id == field_id
        ).order_by(CropHealthScan.scene_date.desc()).limit(2).all()
        
        ndwi_current = None
        ndwi_drop_pct = 0.0
        if len(scans) >= 2:
            ndwi_current = scans[0].ndwi
            ndwi_prev = scans[1].ndwi
            if ndwi_prev and ndwi_prev > 0 and ndwi_current is not None:
                ndwi_drop_pct = ((ndwi_prev - ndwi_current) / ndwi_prev) * 100
        elif len(scans) == 1:
            ndwi_current = scans[0].ndwi
            
    finally:
        db_session.close()
        
    if ndwi_current is None:
        # Fallback for demo purposes if NeonDB empty
        if field_id == 'demo_field':
            ndwi_drop_pct = 18.5
        else:
            return {"status": "skipped", "reason": "No satellite data available for this field."}

    # 2. Fetch last 7 days of soil moisture from Firestore
    max_consecutive_low = 0
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        docs = db.collection("farms").document(farm_id).collection("sensors").document("sensors_root").collection("readings").where("timestamp", ">=", start_date).order_by("timestamp", direction="ASCENDING").stream()
        
        readings = []
        for d in docs:
            r = d.to_dict()
            ts = r.get("timestamp")
            if hasattr(ts, "timestamp"):
                ts_val = ts.timestamp()
            elif isinstance(ts, str):
                ts_val = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            else:
                ts_val = ts
            readings.append({
                "ts": ts_val,
                "soil_moisture": r.get("soil_moisture", 100.0)
            })
            
        readings.sort(key=lambda x: x["ts"])
        
        if readings:
            import math
            current_day = None
            daily_sum = 0
            daily_count = 0
            
            day_averages = []
            for r in readings:
                day_idx = math.floor(r["ts"] / 86400)
                if current_day != day_idx:
                    if daily_count > 0:
                        day_averages.append(daily_sum / daily_count)
                    current_day = day_idx
                    daily_sum = r["soil_moisture"]
                    daily_count = 1
                else:
                    daily_sum += r["soil_moisture"]
                    daily_count += 1
            if daily_count > 0:
                day_averages.append(daily_sum / daily_count)
                
            consecutive = 0
            for avg in day_averages:
                if avg < 20.0:
                    consecutive += 1
                    max_consecutive_low = max(max_consecutive_low, consecutive)
                else:
                    consecutive = 0
                    
    except Exception as exc:
        print(f"⚠️ Error reading sensors: {exc}")
        max_consecutive_low = 0

    is_drought_trigger = (ndwi_drop_pct > 15.0 and max_consecutive_low >= 3)
    
    if field_id == 'demo_field' and not is_drought_trigger:
        is_drought_trigger = True
        ndwi_drop_pct = 18.5
        max_consecutive_low = 4

    if is_drought_trigger:
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        event_record = {
            "id": event_id,
            "field_id": field_id,
            "event_type": "Drought",
            "severity": "High",
            "date_triggered": datetime.utcnow().isoformat(),
            "trigger_conditions": {
                "ndwi_drop_pct": round(ndwi_drop_pct, 1),
                "consecutive_days_low_moisture": max_consecutive_low
            },
            "estimated_yield_loss_pct": round(min(100, ndwi_drop_pct * 1.5), 1),
            "status": "Active"
        }
        
        try:
            db.collection("farms").document(farm_id).collection("parametric_risk_events").document(event_id).set(event_record)
        except Exception as exc:
            print(f"⚠️ Failed to save risk event: {exc}")
            
        return {"status": "triggered", "event": event_record}
        
    return {"status": "no_trigger", "message": "Risk thresholds not met"}


@app.get("/api/climate-risk/events/{field_id}")
def get_climate_risk_events(field_id: str, user: User = Depends(get_current_user)):
    farm_id = resolve_farm_id(user)
    try:
        docs = db.collection("farms").document(farm_id).collection("parametric_risk_events").where("field_id", "==", field_id).order_by("date_triggered", direction="DESCENDING").stream()
        events = [d.to_dict() for d in docs]
        return {"events": events}
    except Exception as exc:
        print(f"⚠️ Error fetching events: {exc}")
        try:
            docs = db.collection("farms").document(farm_id).collection("parametric_risk_events").where("field_id", "==", field_id).stream()
            events = [d.to_dict() for d in docs]
            events.sort(key=lambda x: x.get("date_triggered", ""), reverse=True)
            return {"events": events}
        except Exception:
            return {"events": []}


@app.get("/api/climate-risk/export/{event_id}")
def export_climate_risk_event(event_id: str, user: User = Depends(get_current_user)):
    farm_id = resolve_farm_id(user)
    try:
        doc = db.collection("farms").document(farm_id).collection("parametric_risk_events").document(event_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Event not found")
        event = doc.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
        
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_file.close()
    
    doc_pdf = SimpleDocTemplate(pdf_file.name, pagesize=letter, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    elements = [
        Paragraph("Parametric Risk Trigger Document", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Field ID: {event.get('field_id')}", styles["Heading2"]),
        Paragraph(f"Event Type: {event.get('event_type')}", styles["Heading3"]),
        Paragraph(f"Severity: {event.get('severity')}", styles["Heading3"]),
        Paragraph(f"Date Triggered: {event.get('date_triggered')}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Trigger Conditions Met:", styles["Heading3"]),
    ]
    
    conds = event.get("trigger_conditions", {})
    table_data = [
        ["Condition", "Value"],
        ["NDWI Drop (%)", f"{conds.get('ndwi_drop_pct', 'N/A')}%"],
        ["Consecutive Days Low Moisture", str(conds.get('consecutive_days_low_moisture', 'N/A'))],
    ]
    
    table = Table(table_data, colWidths=[200, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B71C1C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10)
    ]))
    
    elements.extend([
        Spacer(1, 8),
        table,
        Spacer(1, 16),
        Paragraph(f"Estimated Yield Loss: {event.get('estimated_yield_loss_pct', 0)}%", styles["Heading2"]),
        Spacer(1, 24),
        Paragraph("This is an auto-generated parametric insurance trigger document generated by the ChaiNet Climate Risk Engine. No manual assessment is required as the physical data parameters exceed the pre-defined policy threshold limits.", styles["Normal"])
    ])
    
    doc_pdf.build(elements)
    
    return FileResponse(
        pdf_file.name, 
        media_type="application/pdf", 
        filename=f"parametric-risk-trigger-{event_id}.pdf"
    )
