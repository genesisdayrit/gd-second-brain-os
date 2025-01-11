import redis
import requests

# Redis connection
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

def test_gmail_api():
    """Fetch Gmail labels using the access token stored in Redis."""
    # Get the access token from Redis
    access_token = redis_client.get("gmail_access_token")

    if not access_token:
        print("No access token found in Redis. Make sure to authenticate and store tokens first.")
        return

    # Gmail API endpoint to fetch labels
    url = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Make the API request
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        labels = response.json().get("labels", [])
        print("Gmail Labels:")
        for label in labels:
            print(f"- {label['name']}")
    elif response.status_code == 401:
        print("Access token expired or invalid. Please refresh the token.")
    else:
        print(f"Failed to fetch Gmail labels. Status Code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_gmail_api()
