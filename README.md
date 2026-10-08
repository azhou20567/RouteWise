# RouteWise

RouteWise is an AI-assisted school bus route optimization platform designed to identify inefficient routes and recommend improvements. It combines route optimization algorithms, interactive maps, and AI-generated analysis to help evaluate transportation efficiency.

## Features

- **Route Optimization:** Uses Google OR-Tools to optimize school bus routes and reduce travel distance.
- **Interactive Maps:** Visualizes existing and optimized routes using Google Maps.
- **AI-Powered Analysis:** Uses Anthropic Claude to identify route inefficiencies and explain recommended changes.
- **Performance Metrics:** Compares route distance, travel time, costs, and estimated CO₂ emissions.
- **Scenario Comparison:** Allows users to switch between current and optimized routes.
- **Fallback Recommendations:** Provides rule-based recommendations when the AI API is unavailable.

## Tech Stack

- **Frontend:** Next.js, React, TypeScript
- **Backend:** Python, FastAPI, Pydantic
- **AI:** Anthropic Claude API
- **Optimization:** Google OR-Tools
- **Mapping:** Google Maps API
- **Other:** Model Context Protocol (MCP)

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+
- Google Maps API key
- Anthropic API key (optional)

### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file using the provided `.env.example` and configure any required API keys.

4. Start the server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend

1. Open another terminal and navigate to the frontend:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create `.env.local` from `.env.local.example` and configure your Google Maps API key.

4. Start the frontend:
   ```bash
   npm run dev
   ```

5. Visit `http://localhost:3000/` in your browser.

## How It Works

1. Select a school or transportation dataset.
2. View existing routes and performance metrics.
3. Compare existing routes with precomputed optimized routes.
4. Generate AI-powered analysis and recommendations.
5. Review potential improvements in distance, cost, and efficiency.

## Future Improvements

- Support for additional school districts
- Real-time traffic integration
- More advanced routing constraints
