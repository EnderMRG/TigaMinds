# CHAI-NET

> **Intelligent Tea Garden Management for Assam**

CHAI-NET is a sophisticated, data-driven platform designed to modernize tea cultivation in Assam. By combining real-time IoT sensor data, machine learning for disease prediction, and market price forecasting, CHAI-NET empowers estate managers to make optimal decisions—from the leaf to the auction.

## Features

- **Cinematic Landing Experience**: A highly optimized, scroll-driven canvas animation showcasing the product story without heavy third-party libraries.
- **IoT Sensor Integration**: Monitors soil moisture, temperature, and critical environmental metrics.
- **Disease Prediction**: Utilizes Scikit-learn (Random Forest) to predict crop disease risks before they escalate.
- **Market Forecasting**: Tracks Guwahati auction prices and predicts demand volatility.
- **AI Insights**: Integrated with Gemini to provide natural language insights based on real-time cultivation metrics.
- **Pre-populated Demo Mode**: Instantly experience the dashboard with real-world simulated data—no account required.

## Tech Stack

### Frontend
- **Framework**: Next.js (React)
- **Styling**: Tailwind CSS
- **Animation**: Pure CSS & Native HTML5 Canvas (Hardware-accelerated, DPR-aware rendering)

### Backend
- **Framework**: FastAPI (Python)
- **Machine Learning**: Scikit-learn, Pandas
- **AI**: Google Generative AI (Gemini)
- **Authentication**: Firebase Admin

## Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Firebase Admin credentials

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/tigaminds.git
   cd tigaminds
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
   *Create a `.env` file in the `backend` directory with your Gemini API key and Firebase credentials.*
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
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## Design Philosophy

The interface is built following strict, high-end editorial design principles:
- **Asymmetrical Layouts**: Moving away from generic grid structures.
- **Purposeful Motion**: Scroll-driven storytelling driven natively by browser scroll events.
- **Data Clarity**: Presenting thousands of signals (moisture, pricing, disease) with absolute clarity and zero visual clutter.

## License
© 2024 CHAI-NET. Built for Assam.
