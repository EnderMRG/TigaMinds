import { initializeApp, getApps, FirebaseApp } from "firebase/app";
import { getAuth, Auth, GoogleAuthProvider } from "firebase/auth";
import { getFirestore, Firestore } from "firebase/firestore";

// Firebase configuration for chainet-29013
const firebaseConfig = {
  apiKey: "AIzaSyBUcui5L8jvFUHJQSiwvXmL51t3gN5vABM",
  authDomain: "chainet-29013.firebaseapp.com",
  projectId: "chainet-29013",
  storageBucket: "chainet-29013.firebasestorage.app",
  messagingSenderId: "407235215489",
  appId: "1:407235215489:web:05ecba56225542310e4d80",
  measurementId: "G-CNWVZM0ZKB"
};

// Initialize Firebase
const app: FirebaseApp =
  getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];

// Initialize services
export const auth: Auth = getAuth(app);
export const db: Firestore = getFirestore(app);
export const googleProvider = new GoogleAuthProvider();
