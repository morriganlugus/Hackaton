langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import json
import re
import csv
import os
import uuid
import folium
import requests
import webbrowser
import pandas as pd

# ===== CONFIGURATION =====
OPENROUTESERVICE_API_KEY = "" 
CSV_FILE = "conversaciones.csv"
OPENROUTESERVICE_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
llm_key = ""
llm = ChatOpenAI(api_key=llm_key, model="gpt-4o", temperature=0.7)

# Files with routes and anomalies
CSV_ROUTES = "/content/CSV_Routes_with_Hours.csv"
CSV_ANOMALIES = "/content/CSV_Anomalies_with_ID.csv"

# Load CSVs
df_routes = pd.read_csv(CSV_ROUTES)
df_anomaly = pd.read_csv(CSV_ANOMALIES)

# ===== CSV CONVERSATION HANDLING =====
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["conversation_id", "origin", "destination", "anomaly_time", "question", "answer"])

def save_to_csv(conversation_id, origin, destination, anomaly_time, question, answer):
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([conversation_id, origin, destination, anomaly_time, question, answer])

# ===== GET DRIVER INFO =====
def get_driver_info(origin, destination):
    anomaly_row = df_anomaly[
        (df_anomaly['Origin City'].str.lower() == origin.lower()) &
        (df_anomaly['Destination City'].str.lower() == destination.lower())
    ]

    if anomaly_row.empty:
        return None, None, None, None, None

    anomaly_id = int(anomaly_row['id_anomaly'].values[0])
    route_row = df_routes[df_routes['id_ruta'] == anomaly_id]

    if route_row.empty:
        return anomaly_id, None, None, None, None

    truck_number = route_row['truck_number'].values[0]
    driver = route_row['driver'].values[0]
    departure_time = route_row['departure_time'].values[0]
    arrival_time = route_row['arrival_time'].values[0]

    return anomaly_id, truck_number, driver, departure_time, arrival_time

# ===== UPDATE ETA IN CSV =====
def update_eta(origin, destination, new_eta):
    try:
        df_local = pd.read_csv(CSV_ROUTES)
        row = (df_local['Origin City'].str.lower() == origin.lower()) & \
              (df_local['Destination City'].str.lower() == destination.lower())

        if row.any():
            df_local.loc[row, 'arrival_time'] = new_eta
            df_local.to_csv(CSV_ROUTES, index=False)
            print(f"✅ ETA updated to {new_eta} for {origin} → {destination}")
        else:
            print("❌ Route not found in the CSV.")
    except Exception as e:
        print(f"Error updating the CSV: {e}")

# ===== GPT FUNCTIONS =====
def extract_route_info(driver_response):
    system_prompt = (
        "You are an assistant that extracts structured information from driver messages. "
        "Return ONLY a valid JSON with keys: 'cause', 'new_route', 'new_eta'. If something is missing, set it to null. "
        "Example: {\"cause\": \"accident\", \"new_route\": [\"City A\", \"City B\"], \"new_eta\": \"18:30\"}"
    )
    user_prompt = f"Driver message: {driver_response}"
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    try:
        response = llm.invoke(messages)
        data = json.loads(response.content)

        if data.get("new_route") and isinstance(data["new_route"], str):
            data["new_route"] = [x.strip() for x in data["new_route"].split(",")]

        if data.get("new_eta") and not re.match(r"^\d{2}:\d{2}$", data["new_eta"]):
            data["new_eta"] = None

        return data
    except:
        return {"cause": None, "new_route": None, "new_eta": None}

def cordial_response(driver_response):
    system_prompt = (
        "You are a friendly assistant responding to a driver. "
        "Acknowledge their response, thank them, and offer help if necessary."
    )
    user_prompt = f"Driver said: {driver_response}"
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    try:
        response = llm.invoke(messages)
        return response.content
    except:
        return "Thanks for the update, I’ll keep that in mind!"

# ===== MAP GENERATION =====
def generate_real_route_map(new_route, conversation_id):
    if not new_route or len(new_route) < 2:
        print("❌ Cannot generate map: route is incomplete.")
        return None

    coords = []
    for place in new_route:
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={place}"
            resp = requests.get(url, headers={'User-Agent': 'route-mapper'})
            if resp.status_code == 200 and resp.json():
                lat = float(resp.json()[0]["lat"])
                lon = float(resp.json()[0]["lon"])
                coords.append([lon, lat])
        except:
            continue

    if len(coords) < 2:
        print("❌ Not enough coordinates found.")
        return None

    headers = {"Authorization": OPENROUTESERVICE_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": coords}
    route_resp = requests.post(OPENROUTESERVICE_URL, headers=headers, json=body)

    if route_resp.status_code != 200:
        print(" ORS Error:", route_resp.text)
        return None

    data_route = route_resp.json()
    geometry = data_route["features"][0]["geometry"]["coordinates"]
    route_latlon = [(lat, lon) for lon, lat in geometry]

    map_obj = folium.Map(location=route_latlon[0], zoom_start=6)
    folium.PolyLine(route_latlon, color="blue", weight=5).add_to(map_obj)
    folium.Marker(route_latlon[0], popup="Start", icon=folium.Icon(color="green")).add_to(map_obj)
    folium.Marker(route_latlon[-1], popup="Destination", icon=folium.Icon(color="red")).add_to(map_obj)

    map_path = f"real_route_{conversation_id}.html"
    map_obj.save(map_path)
    webbrowser.open(map_path)

    print(f"New roadMap generated: {map_path}")

# ===== MAIN INTERACTION =====
def complete_driver_info(origin, destination, anomaly_time):
    info = {"cause": None, "new_route": None, "new_eta": None}
    conversation_id = str(uuid.uuid4())

    # Personalization
    anomaly_id, truck_number, driver, departure_time, arrival_time = get_driver_info(origin, destination)
    if truck_number and driver:
        initial_message = (
            f"Hello {driver}! We know you are driving truck {truck_number}. "
            f"You departed at {departure_time} and your estimated arrival was {arrival_time}. "
            f"We detected a deviation between {origin} and {destination} at {anomaly_time}. "
            "What happened? Where are you now? What is your new ETA?"
        )
    else:
        initial_message = (
            f"Hello! We detected a deviation between {origin} and {destination} at {anomaly_time}. "
            "What happened? Where are you now? What is your new ETA?"
        )

    while None in info.values():
        missing_parts = [k for k, v in info.items() if v is None]
        question = initial_message if len(missing_parts) == 3 else "I still need this info: " + " ".join(
            [("Why did you deviate?" if "cause" in missing_parts else ""),
             ("What is the new route?" if "new_route" in missing_parts else ""),
             ("What is the new ETA?" if "new_eta" in missing_parts else "")]
        )

        print(question)
        response = input("Your response: ")
        save_to_csv(conversation_id, origin, destination, anomaly_time, question, response)
        print(cordial_response(response))

        new_data = extract_route_info(response)
        for key in info:
            if info[key] is None and new_data.get(key):
                info[key] = new_data[key]

        if new_data.get("new_eta"):
            update_eta(origin, destination, new_data["new_eta"])

    print("Do you need extra help? If yes, assistance will be sent.")
    if input("Your response: ").strip().lower() in ["yes", "sure", "please", "affirmative"]:
        print("Perfect, help is on the way 🚐")

    return info, conversation_id

def create_customer_message(cause, new_eta, new_route):
    system_prompt = (
        "You are an assistant for Traffic Tech drafting messages for customers in a polite, formal tone. "
        "Explain the cause, the new ETA, and the new route."
        "Sign as Jose Daniel Alejandro Guzman, IA Engineer"
    )
    user_prompt = f"Cause: {cause}\nNew ETA: {new_eta}\nNew route: {new_route}"
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    try:
        response = llm.invoke(messages)
        return response.content
    except:
        return "Could not generate customer message."
