### Redis Setup
1. get_auth_code.py --> gets the initial auth code from local call back URL for authorization
2. initial_redis_setup.py --> sets up redis and stores spotify access and refresh tokens. enter auth code in console.
3. refresh_redis_token.py --> refreshes spotify access token using refresh token
4. schedule cron job to run refresh_redis_token.py every 55 minutes or <1 hour to keep refresh token fresh