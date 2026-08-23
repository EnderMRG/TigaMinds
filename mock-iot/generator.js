const admin = require("firebase-admin");
const serviceAccount = require("./serviceAccountKey.json");

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

const FARM_ID = "demo_farm";

function generateReading() {
  return {
    soil_moisture: +(30 + Math.random() * 20).toFixed(1), // 30–50 %
    temperature: +(22 + Math.random() * 10).toFixed(1),   // 22–32 °C
    humidity: +(65 + Math.random() * 25).toFixed(1),      // 65–90 %
    rainfall_7d: +(10 + Math.random() * 90).toFixed(1),   // 10–100 mm
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
  };
}

async function pushReading() {
  const ref = db
    .collection("farms")
    .doc(FARM_ID)
    .collection("sensors")
    .doc("sensors_root")
    .collection("readings");

  await ref.add(generateReading());
  console.log("📡 New sensor data pushed");
}

setInterval(pushReading, 7000); // every 7 seconds
