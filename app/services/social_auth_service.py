import logging
from typing import Optional, Tuple
from dataclasses import dataclass
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SocialUserInfo:
    """Standardized user info from social providers"""
    provider_user_id: str
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    profile_data: dict


class SocialAuthService:
    def __init__(self):
        self.google_client_id = settings.GOOGLE_CLIENT_ID
        self.facebook_app_id = settings.FACEBOOK_APP_ID
        self.facebook_app_secret = settings.FACEBOOK_APP_SECRET

    async def verify_google_token(self, token: str) -> SocialUserInfo:
        """
        Verify Google ID token and extract user info.
        For mobile apps, the token is the ID token from Google Sign-In SDK.
        """
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self.google_client_id
            )

            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError("Invalid token issuer")

            # Extract user info
            return SocialUserInfo(
                provider_user_id=idinfo['sub'],
                email=idinfo.get('email', ''),
                first_name=idinfo.get('given_name', ''),
                last_name=idinfo.get('family_name', ''),
                email_verified=idinfo.get('email_verified', False),
                profile_data={
                    'picture': idinfo.get('picture'),
                    'locale': idinfo.get('locale'),
                    'name': idinfo.get('name')
                }
            )

        except ValueError as e:
            logger.error(f"Google token verification failed: {str(e)}")
            raise ValueError(f"Invalid Google token: {str(e)}")

    async def verify_facebook_token(self, access_token: str) -> SocialUserInfo:
        """
        Verify Facebook access token and fetch user info.
        For mobile apps, the token is the access token from Facebook SDK.
        """
        try:
            async with httpx.AsyncClient() as client:
                # First, verify the token with Facebook's debug endpoint
                debug_url = "https://graph.facebook.com/debug_token"
                debug_response = await client.get(
                    debug_url,
                    params={
                        "input_token": access_token,
                        "access_token": f"{self.facebook_app_id}|{self.facebook_app_secret}"
                    }
                )
                debug_response.raise_for_status()
                debug_data = debug_response.json()

                if not debug_data.get("data", {}).get("is_valid", False):
                    raise ValueError("Invalid Facebook token")

                # Verify the app ID matches
                if debug_data["data"].get("app_id") != self.facebook_app_id:
                    raise ValueError("Token was not issued for this app")

                user_id = debug_data["data"]["user_id"]

                # Fetch user profile
                profile_url = f"https://graph.facebook.com/v18.0/{user_id}"
                profile_response = await client.get(
                    profile_url,
                    params={
                        "fields": "id,email,first_name,last_name,name,picture",
                        "access_token": access_token
                    }
                )
                profile_response.raise_for_status()
                profile_data = profile_response.json()

                return SocialUserInfo(
                    provider_user_id=profile_data['id'],
                    email=profile_data.get('email', ''),
                    first_name=profile_data.get('first_name', ''),
                    last_name=profile_data.get('last_name', ''),
                    email_verified=True,  # Facebook requires verified email
                    profile_data={
                        'picture': profile_data.get('picture', {}).get('data', {}).get('url'),
                        'name': profile_data.get('name')
                    }
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API error: {str(e)}")
            raise ValueError(f"Facebook API error: {str(e)}")
        except Exception as e:
            logger.error(f"Facebook token verification failed: {str(e)}")
            raise ValueError(f"Invalid Facebook token: {str(e)}")


social_auth_service = SocialAuthService()
