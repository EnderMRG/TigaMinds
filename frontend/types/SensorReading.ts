import { Timestamp } from "firebase/firestore";

export interface SensorReading {
  soil_moisture: number;
  temperature: number;
  humidity: number;
  rainfall_7d: number;
  timestamp: Timestamp;
}
