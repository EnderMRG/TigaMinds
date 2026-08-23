# CHAI-NET

> **Intelligent Tea Garden Management for Assam**

CHAI-NET is a sophisticated, data-driven platform designed to modernize tea cultivation in Assam. By combining real-time IoT sensor data, machine learning for disease prediction (including YOLOv5 and Scikit-learn), and market price forecasting, CHAI-NET empowers estate managers to make optimal decisions—from the leaf to the auction. 

Built with the core principle of **"One screen, one decision,"** CHAI-NET ingests complex data and distils it into a single prioritized action plan.

## ✨ Key Capabilities

- **Integrated IoT & AI**: Ingests real-time sensor data (soil moisture, temperature, humidity, rainfall) and combines it with AI insights.
- **Computer-Vision Disease Detection**: Upload leaf scans directly from the field via mobile to detect diseases using locally calibrated YOLOv5 + CNN models.
- **Market Forecasting**: Predicts Guwahati auction prices and demand volatility using historical data to help managers decide when to sell.
- **Worker SMS Alerts**: Integrated with Twilio to push real-time alerts to farm supervisors and pluckers when conditions require immediate action.
- **Bilingual Interface**: Native support for English and Assamese to ensure accessibility for all users on the estate.
- **Pre-populated Demo Mode**: Instantly experience a fully populated dashboard using mock local fixtures—no account required.
- **Cinematic Landing Experience**: A highly optimized, scroll-driven canvas animation showcasing the product story without heavy third-party libraries.

## 🛠 Tech Stack

### Frontend
- **Framework**: Next.js (App Router), React, TypeScript
- **Styling**: Tailwind CSS
- **Components & Charts**: shadcn/ui, Recharts
- **Animation**: Pure CSS & Native HTML5 Canvas (Hardware-accelerated)

### Backend & ML
- **Framework**: FastAPI (Python)
- **Machine Learning**: YOLOv5, Scikit-learn, Pandas (Drought/Pest prediction & Leaf classification)
- **AI**: Google Generative AI (Gemini) for natural language insights
- **Database & Auth**: Firebase Firestore, Firebase Auth (Google Sign-In)
- **Communications**: Twilio for SMS alerts

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Firebase Admin credentials
- Gemini API Key
- Twilio Account (for SMS features)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/EnderMRG/TigaMinds.git
   cd tigaminds
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv .venv
   
   # Activate virtual environment
   # Windows:
   .venv\Scripts\activate  
   # macOS/Linux:
   # source .venv/bin/activate
   
   pip install -r requirements.txt
   ```
   *Create a `.env` file in the `backend` directory with your Gemini API key, Twilio credentials, and Firebase config.*
   ```bash
   # Run the development server
   uvicorn main:app --reload
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **View the App**
   Open [http://localhost:3000](http://localhost:3000) in your browser. The app includes a demo mode that uses backend fixtures, so you can explore the dashboard even if external APIs hit rate limits.

## 🎯 Product Principles

1. **One screen, one decision**: The dashboard surfaces clear recommended actions, avoiding raw number clutter.
2. **Locally calibrated**: Assam-specific disease models and Guwahati auction data ensure relevance.
3. **Always alive**: With demo mode, fallback fixtures, and graceful Gemini rate-limit handling, the product never shows a blank screen.
4. **Field-first**: Designed for scannability and decisive action during a morning check on a laptop or tablet.
5. **Trust through transparency**: Confidence scores and AI attribution prevent blind reliance on model outputs.

## 📜 License
© 2024 CHAI-NET. Built for Assam.
