# Traffic Tech AI System

This Python application uses **LangChain**, **OpenAI GPT**, and **OpenRouteService** to manage logistics anomalies by interacting with drivers and generating reports for customers.

---

## **Features**
- Detect deviations in planned routes.
- Interactive Q&A with drivers (in English).
- Extract structured data from unstructured driver responses using GPT.
- Update Estimated Time of Arrival (ETA) in CSV.
- Generate real route map with OpenStreetMap and OpenRouteService.
- Draft formal messages for customers automatically.
- Track metrics like response time and execution time.

---

## **Folder Structure**
```
project/
│── main.py                     # Main script
│── CSV_Routes_with_Hours.csv   # Routes and driver info
│── CSV_Anomalies_with_ID.csv   # Anomalies linked to routes
│── conversations.csv           # Logs of driver interactions
│── README.md                   # Documentation
```

---

## **Inputs**
- `CSV_Routes_with_Hours.csv`
  ```
  id_route,Origin City,Destination City,truck_number,driver,departure_time,arrival_time
  ```
- `CSV_Anomalies_with_ID.csv`
  ```
  id_anomaly,Origin City,Destination City
  ```

---

## **Outputs**
- `conversations.csv` → Stores interaction logs.
- `real_route_<id>.html` → Interactive route map.
- **Customer Message** → Generated automatically and displayed in console.

---

## **How to Run**
1. Install dependencies:
   ```bash
   pip install langchain-openai pandas folium requests
   ```
2. Set your API keys:
   - `OPENROUTESERVICE_API_KEY` → From OpenRouteService.
   - `llm_key` → Your OpenAI API Key.
3. Run the main script:
   ```bash
   python main.py
   ```
4. Follow the prompts to simulate the driver conversation.
5. Check:
   - `conversations.csv` for logs.
   - Browser for the generated map.
   - Console for the client message.

---

## **Metrics**
- Measures:
  - Time per GPT response.
  - Total driver interaction time.
  - Total execution time.
