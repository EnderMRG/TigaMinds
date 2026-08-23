"use client";

import { useEffect, useState } from "react";
import {
  collection,
  query,
  orderBy,
  limit,
  onSnapshot,
} from "firebase/firestore";
import { db } from "../lib/firebase";
import type { SensorReading } from "../types/SensorReading";

export default function LiveSensors() {
  const [data, setData] = useState<SensorReading | null>(null);

  useEffect(() => {
    const q = query(
      collection(
        db,
        "farms",
        "demo_farm",
        "sensors",
        "sensors_root",
        "readings"
      ),
      orderBy("timestamp", "desc"),
      limit(1)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      if (!snapshot.empty) {
        setData(snapshot.docs[0].data() as SensorReading);
      }
    });

    return () => unsubscribe();
  }, []);

  if (!data) return <p>Loading live sensor data…</p>;

  return (
    <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 8 }}>
      <h2>🌱 Live Farm Sensors</h2>
      <p>Soil Moisture: {data.soil_moisture}%</p>
      <p>Temperature: {data.temperature} °C</p>
      <p>Humidity: {data.humidity}%</p>
      <p>Rainfall (7 days): {data.rainfall_7d} mm</p>
    </div>
  );
}
