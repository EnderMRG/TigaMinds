
const admin = require("firebase-admin");
console.log("🚀 Backfill script started");
const serviceAccount = require("./serviceAccountKey.json");

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

const FARM_ID = "demo_farm";
const DAYS = 15;
const HOURS_PER_DAY = 24;

// 🔒 FIXED BASE DATE → 2026
const BASE_DATE = new Date("2026-01-30T23:00:00"); // adjust if needed

function random(min, max, decimals = 1) {
  return +(min + Math.random() * (max - min)).toFixed(decimals);
}

// Assam-realistic hourly climate model
function generateAssamReading(date) {
  const hour = date.getHours();

  // Day–night temperature cycle
  const temperature =
    hour >= 6 && hour <= 16
      ? random(24, 32)   // daytime
      : random(18, 24);  // night

  // Humidity inversely related to temperature
  const humidity =
    hour >= 6 && hour <= 16
      ? random(65, 80)
      : random(75, 90);

  const soil_moisture = random(45, 70);

  // Occasional rainfall spikes
  const rainfall_7d =
    Math.random() < 0.25
      ? random(40, 120)
      : random(20, 60);

  return {
    soil_moisture,
    temperature,
    humidity,
    rainfall_7d,
    timestamp: admin.firestore.Timestamp.fromDate(date),
  };
}

async function backfill() {
  const ref = db
    .collection("farms")
    .doc(FARM_ID)
    .collection("sensors")
    .doc("sensors_root")
    .collection("readings");

  const batch = db.batch();
  let count = 0;

  for (let dayOffset = DAYS - 1; dayOffset >= 0; dayOffset--) {
    for (let hour = 0; hour < HOURS_PER_DAY; hour++) {
      const date = new Date(BASE_DATE);
      date.setDate(BASE_DATE.getDate() - dayOffset);
      date.setHours(hour, 0, 0, 0);

      const docRef = ref.doc();
      batch.set(docRef, generateAssamReading(date));
      count++;
    }
  }

  await batch.commit();
  console.log(`✅ Uploaded ${count} hourly readings for Jan 2026`);
}

backfill().catch(console.error);
