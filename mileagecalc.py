##IRS Mileage Calc
import os
import sys
import requests

# === CONFIG ===
IRS_BUSINESS_RATE = 0.70  # dollars per mile (update annually)
GOOGLE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


def safe_input(prompt: str) -> str:
    """
    Wrapper around input() to gracefully handle KeyboardInterrupt / EOFError.
    """
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print("\nInput cancelled by user. Exiting.")
        sys.exit(1)


def get_api_key() -> str:
    """Get the Google Maps API key from the environment."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_MAPS_API_KEY environment variable is not set.")
        print("Set it with: export GOOGLE_MAPS_API_KEY='YOUR_KEY_HERE'")
        sys.exit(1)
    return api_key


def prompt_for_addresses():
    """
    Interactively get origin and stops from the user with robust error handling.

    - Requires a non-empty origin.
    - Requires at least one stop.
    - Allows user to type 'q', 'quit', or 'exit' to cancel.
    """
    # --- Origin ---
    while True:
        print("Enter your starting address (origin):")
        origin = safe_input("> ").strip()

        if origin.lower() in {"q", "quit", "exit"}:
            print("User requested exit. Goodbye.")
            sys.exit(0)

        if origin:
            break
        else:
            print("Origin cannot be empty. Please enter a valid starting address.\n")

    # --- Stops (at least one) ---
    while True:
        print(
            "\nNow enter each stop.\n"
            "- Press ENTER on a blank line or type 'done' when you're finished.\n"
            "- Type 'q' to cancel and exit.\n"
        )

        stops = []
        while True:
            stop = safe_input(f"Stop #{len(stops) + 1}: ").strip()

            # Handle special commands
            lower = stop.lower()
            if lower in {"q", "quit", "exit"}:
                print("User requested exit. Goodbye.")
                sys.exit(0)
            if lower in {"", "done"}:
                break

            # Non-empty stop
            stops.append(stop)

        if len(stops) == 0:
            print(
                "\nNo stops entered. You must enter at least one destination.\n"
                "Let's try entering your stops again.\n"
            )
            continue

        # We have at least one stop; proceed
        if len(stops) == 1:
            destination = stops[0]
            waypoints = []
        else:
            destination = stops[-1]
            waypoints = stops[:-1]

        return origin, destination, waypoints


def build_directions_params(origin, destination, waypoints, api_key):
    """Build query parameters for the Google Directions API."""
    params = {
        "origin": origin,
        "destination": destination,
        "mode": "driving",
        "key": api_key
    }

    if waypoints:
        # optimize:true asks Google to find the best order for the stops
        waypoints_str = "optimize:true|" + "|".join(waypoints)
        params["waypoints"] = waypoints_str

    return params


def get_directions(origin, destination, waypoints, api_key):
    """Call the Google Directions API and return the JSON response."""
    params = build_directions_params(origin, destination, waypoints, api_key)
    response = requests.get(GOOGLE_DIRECTIONS_URL, params=params, timeout=15)

    if response.status_code != 200:
        print(f"HTTP error from Google Directions API: {response.status_code}")
        print(response.text[:500])
        sys.exit(1)

    data = response.json()
    if data.get("status") != "OK":
        print(f"Google Directions API returned status: {data.get('status')}")
        print("Details:", data.get("error_message"))
        sys.exit(1)

    return data


def extract_total_distance_meters(directions_json) -> int:
    """
    Sum the distance over all legs of the route.
    distance.value is in meters.
    """
    total_meters = 0
    routes = directions_json.get("routes", [])
    if not routes:
        print("No routes found in Directions API response.")
        sys.exit(1)

    # Take the first route (Google's best)
    legs = routes[0].get("legs", [])
    if not legs:
        print("No legs found in the route.")
        sys.exit(1)

    for leg in legs:
        dist_value = leg.get("distance", {}).get("value")
        if dist_value is None:
            print("Missing distance value in one of the legs.")
            sys.exit(1)
        total_meters += dist_value

    return total_meters


def meters_to_miles(meters: float) -> float:
    return meters / 1609.344  # 1 mile = 1609.344 meters


def get_optimized_order(directions_json, origin, destination, waypoints):
    """
    Return the ordered list of addresses in the optimized route.
    - For optimized waypoints, Google returns 'waypoint_order' as indices
      into the original waypoint list.
    """
    route = directions_json["routes"][0]
    ordered = [origin]

    if "waypoint_order" in route and waypoints:
        ordered_indices = route["waypoint_order"]
        for idx in ordered_indices:
            if 0 <= idx < len(waypoints):
                ordered.append(waypoints[idx])
            else:
                # Fallback: index out of range, just ignore
                continue

    ordered.append(destination)
    return ordered


def main():
    print("=== Mileage & IRS Reimbursement Calculator ===\n")

    api_key = get_api_key()
    origin, destination, waypoints = prompt_for_addresses()

    print("\nCalculating best route and distance via Google Maps...\n")
    directions_json = get_directions(origin, destination, waypoints, api_key)

    total_meters = extract_total_distance_meters(directions_json)
    total_miles = meters_to_miles(total_meters)
    reimbursement = total_miles * IRS_BUSINESS_RATE

    ordered_stops = get_optimized_order(directions_json, origin, destination, waypoints)

    print("Optimized Route Order:")
    for i, addr in enumerate(ordered_stops, start=1):
        print(f"  {i}. {addr}")

    print("\nTotals:")
    print(f"  Total distance: {total_miles:.2f} miles")
    print(f"  IRS business rate: ${IRS_BUSINESS_RATE:.2f} per mile")
    print(f"  Reimbursement amount: ${reimbursement:,.2f}")

    print("\nNote: Update IRS_BUSINESS_RATE in future years as needed.")


if __name__ == "__main__":
    main()
