from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import KeycloakError
from typing import Dict, Optional, List
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class KeycloakService:
    def __init__(self):
        self.server_url = settings.KEYCLOAK_SERVER_URL
        self.realm_name = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_CLIENT_SECRET
        self.mobile_client_id = settings.KEYCLOAK_MOBILE_CLIENT_ID
        self.mobile_client_secret = settings.KEYCLOAK_MOBILE_CLIENT_SECRET
        
        # Initialize clients as None - they will be created when first accessed
        self._keycloak_admin = None
        self._keycloak_openid = None
        self._mobile_openid = None

    def _get_admin_client(self):
        """Lazy initialization of admin client"""
        if self._keycloak_admin is None:
            try:
                self._keycloak_admin = KeycloakAdmin(
                    server_url=self.server_url,
                    username=settings.KEYCLOAK_ADMIN_USERNAME,
                    password=settings.KEYCLOAK_ADMIN_PASSWORD,
                    realm_name="master",
                    user_realm_name=self.realm_name,
                    verify=False
                )
            except Exception as e:
                logger.error(f"Failed to initialize Keycloak admin client: {e}")
                raise
        return self._keycloak_admin
    
    def _get_openid_client(self):
        """Lazy initialization of OpenID client"""
        if self._keycloak_openid is None:
            self._keycloak_openid = KeycloakOpenID(
                server_url=self.server_url,
                client_id=self.client_id,
                realm_name=self.realm_name,
                client_secret_key=self.client_secret
            )
        return self._keycloak_openid
    
    def _get_mobile_openid_client(self):
        """Lazy initialization of mobile OpenID client"""
        if self._mobile_openid is None:
            self._mobile_openid = KeycloakOpenID(
                server_url=self.server_url,
                client_id=self.mobile_client_id,
                realm_name=self.realm_name,
                client_secret_key=self.mobile_client_secret
            )
        return self._mobile_openid
    
    @property
    def keycloak_admin(self):
        return self._get_admin_client()
    
    @property
    def keycloak_openid(self):
        return self._get_openid_client()
    
    @property
    def mobile_openid(self):
        return self._get_mobile_openid_client()

    async def register_user(self, email: str, password: str, first_name: str, last_name: str) -> Dict:
        """Register a new user in Keycloak using direct API calls"""
        try:
            # Get admin token
            admin_token = await self._get_admin_token()
            
            user_data = {
                "email": email,
                "username": email,
                "enabled": True,
                "firstName": first_name,
                "lastName": last_name,
                "credentials": [
                    {
                        "type": "password",
                        "value": password,
                        "temporary": False
                    }
                ],
                "emailVerified": False,
                "requiredActions": ["VERIFY_EMAIL"]
            }
            
            # Create user via direct API call
            import requests
            headers = {
                'Authorization': f'Bearer {admin_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.server_url}/admin/realms/{self.realm_name}/users",
                json=user_data,
                headers=headers,
                verify=False
            )
            
            if response.status_code == 201:
                # Get the user ID from the Location header
                location = response.headers.get('Location', '')
                user_id = location.split('/')[-1] if location else None
                
                if user_id:
                    # Add user to free-users group by default
                    await self._add_user_to_group_direct(admin_token, user_id, "free-users")
                    
                    # Send verification email
                    await self._send_verification_email_direct(admin_token, user_id)
                
                return {"user_id": user_id, "message": "User created successfully. Please verify your email."}
            else:
                error_msg = response.text
                logger.error(f"User creation failed: {response.status_code} - {error_msg}")
                raise Exception(f"Registration failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            raise Exception(f"Registration failed: {str(e)}")

    async def _get_admin_token(self) -> str:
        """Get admin access token using direct API call"""
        import requests
        
        url = f"{self.server_url}/realms/master/protocol/openid-connect/token"
        data = {
            'grant_type': 'password',
            'username': settings.KEYCLOAK_ADMIN_USERNAME,
            'password': settings.KEYCLOAK_ADMIN_PASSWORD,
            'client_id': 'admin-cli'
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        response = requests.post(url, data=data, headers=headers, verify=False)
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data['access_token']
        else:
            raise Exception(f"Failed to get admin token: {response.status_code} - {response.text}")

    async def _add_user_to_group_direct(self, admin_token: str, user_id: str, group_name: str):
        """Add user to group using direct API call"""
        import requests
        
        # First, find the group ID
        headers = {'Authorization': f'Bearer {admin_token}'}
        groups_response = requests.get(
            f"{self.server_url}/admin/realms/{self.realm_name}/groups?search={group_name}",
            headers=headers,
            verify=False
        )
        
        if groups_response.status_code == 200:
            groups = groups_response.json()
            group = next((g for g in groups if g['name'] == group_name), None)
            
            if group:
                group_id = group['id']
                # Add user to group
                response = requests.put(
                    f"{self.server_url}/admin/realms/{self.realm_name}/users/{user_id}/groups/{group_id}",
                    headers=headers,
                    verify=False
                )
                if response.status_code == 204:
                    logger.info(f"User {user_id} added to group {group_name}")
                else:
                    logger.warning(f"Failed to add user to group: {response.status_code}")
            else:
                logger.warning(f"Group {group_name} not found")

    async def _send_verification_email_direct(self, admin_token: str, user_id: str):
        """Send email verification using direct API call"""
        import requests
        
        headers = {'Authorization': f'Bearer {admin_token}'}
        
        # Send verification email by executing the VERIFY_EMAIL required action
        response = requests.put(
            f"{self.server_url}/admin/realms/{self.realm_name}/users/{user_id}/send-verify-email",
            headers=headers,
            verify=False
        )
        
        if response.status_code == 204:
            logger.info(f"Verification email sent for user {user_id}")
        else:
            logger.warning(f"Failed to send verification email: {response.status_code} - {response.text}")

    async def authenticate_user(self, email: str, password: str) -> Dict:
        """Authenticate user and return tokens"""
        try:
            token = self.mobile_openid.token(email, password)
            return token
        except KeycloakError as e:
            logger.error(f"Authentication failed for {email}: {str(e)}")
            raise Exception("Invalid credentials")

    async def refresh_token(self, refresh_token: str) -> Dict:
        """Refresh access token"""
        try:
            token = self.mobile_openid.refresh_token(refresh_token)
            return token
        except KeycloakError as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise Exception("Token refresh failed")

    async def verify_token(self, token: str) -> Dict:
        """Verify and decode access token"""
        try:
            # Use the same client that issued the tokens (mobile_openid)
            KEYCLOAK_PUBLIC_KEY = (
                "-----BEGIN PUBLIC KEY-----\n"
                + self.mobile_openid.public_key()
                + "\n-----END PUBLIC KEY-----"
            )
            
            options = {"verify_signature": True, "verify_aud": False, "verify_exp": True}
            token_info = self.mobile_openid.decode_token(
                token, key=KEYCLOAK_PUBLIC_KEY, options=options
            )
            return token_info
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise Exception("Invalid token")

    async def logout_user(self, refresh_token: str) -> bool:
        """Logout user by invalidating refresh token"""
        try:
            # Use the same client that issued the tokens (mobile_openid)
            self.mobile_openid.logout(refresh_token)
            return True
        except KeycloakError as e:
            logger.error(f"Logout failed with mobile client: {str(e)}")
            # Fallback: try with direct API call
            try:
                return await self._logout_user_direct(refresh_token)
            except Exception as fallback_error:
                logger.error(f"Direct API logout also failed: {fallback_error}")
                return False

    async def _logout_user_direct(self, refresh_token: str) -> bool:
        """Logout user using direct API call as fallback"""
        import requests
        
        try:
            url = f"{self.server_url}/realms/{self.realm_name}/protocol/openid-connect/logout"
            data = {
                'client_id': self.mobile_client_id,
                'client_secret': self.mobile_client_secret,
                'refresh_token': refresh_token
            }
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            response = requests.post(url, data=data, headers=headers, verify=False)
            
            if response.status_code == 204:
                logger.info("User logged out successfully via direct API")
                return True
            else:
                logger.warning(f"Direct API logout failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error in direct API logout: {str(e)}")
            return False

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user information by ID"""
        try:
            return self.keycloak_admin.get_user(user_id)
        except KeycloakError as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user information by email"""
        try:
            users = self.keycloak_admin.get_users({"email": email})
            return users[0] if users else None
        except KeycloakError as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            return None

    def update_user(self, user_id: str, user_data: Dict) -> bool:
        """Update user information"""
        try:
            self.keycloak_admin.update_user(user_id, user_data)
            return True
        except KeycloakError as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        try:
            self.keycloak_admin.delete_user(user_id)
            return True
        except KeycloakError as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            return False

    def add_user_to_group(self, user_id: str, group_name: str) -> bool:
        """Add user to a group"""
        try:
            groups = self.keycloak_admin.get_groups({"search": group_name})
            if groups:
                group_id = groups[0]["id"]
                self.keycloak_admin.group_user_add(user_id, group_id)
                return True
            return False
        except KeycloakError as e:
            logger.error(f"Error adding user {user_id} to group {group_name}: {str(e)}")
            return False

    def remove_user_from_group(self, user_id: str, group_name: str) -> bool:
        """Remove user from a group"""
        try:
            groups = self.keycloak_admin.get_groups({"search": group_name})
            if groups:
                group_id = groups[0]["id"]
                self.keycloak_admin.group_user_remove(user_id, group_id)
                return True
            return False
        except KeycloakError as e:
            logger.error(f"Error removing user {user_id} from group {group_name}: {str(e)}")
            return False

    async def get_user_groups(self, user_id: str) -> List[Dict]:
        """Get user's groups using direct API call"""
        try:
            admin_token = await self._get_admin_token()
            
            import requests
            headers = {'Authorization': f'Bearer {admin_token}'}
            
            response = requests.get(
                f"{self.server_url}/admin/realms/{self.realm_name}/users/{user_id}/groups",
                headers=headers,
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get user groups: {response.status_code} - {response.text}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting groups for user {user_id}: {str(e)}")
            return []

    async def get_user_by_id_direct(self, user_id: str) -> Optional[Dict]:
        """Get user information by ID using direct API call"""
        try:
            admin_token = await self._get_admin_token()
            
            import requests
            headers = {'Authorization': f'Bearer {admin_token}'}
            
            response = requests.get(
                f"{self.server_url}/admin/realms/{self.realm_name}/users/{user_id}",
                headers=headers,
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get user by ID: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {str(e)}")
            return None

    async def reset_password(self, email: str) -> bool:
        """Send password reset email"""
        try:
            user = self.get_user_by_email(email)
            if user:
                user_id = user["id"]
                self.keycloak_admin.send_update_account(
                    user_id, 
                    ["UPDATE_PASSWORD"]
                )
                return True
            return False
        except KeycloakError as e:
            logger.error(f"Error sending password reset for {email}: {str(e)}")
            return False


# Singleton instance
keycloak_service = KeycloakService()