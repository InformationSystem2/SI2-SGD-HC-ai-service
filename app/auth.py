import os
import base64
import jwt
from pathlib import Path
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db

# Get absolute paths to env files relative to this file
current_file_dir = Path(__file__).parent.resolve()
local_env = current_file_dir.parent / ".env"
spring_env = current_file_dir.parent.parent / "sgd_spring-boot" / ".env"

load_dotenv(dotenv_path=local_env)
load_dotenv(dotenv_path=spring_env)

JWT_SECRET_RAW = os.getenv("JWT_SECRET")
if not JWT_SECRET_RAW:
    JWT_SECRET_RAW = "thatqIsMykeyregrdesawww233eggtwasoddgkjjhhtdhttebd54ndsiuuhhhshs8877465sbbdd"

# Decode secret key from Base64 (matching Spring's Decoders.BASE64.decode)
try:
    missing_padding = len(JWT_SECRET_RAW) % 4
    if missing_padding:
        padded_secret = JWT_SECRET_RAW + '=' * (4 - missing_padding)
    else:
        padded_secret = JWT_SECRET_RAW
    JWT_SECRET = base64.b64decode(padded_secret)
except Exception:
    JWT_SECRET = JWT_SECRET_RAW.encode("utf-8")

security = HTTPBearer()

class CurrentUser:
    def __init__(self, username: str, tenant_id: str, tenant_slug: str, roles: list, permissions: list):
        self.username = username
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.roles = roles
        self.permissions = permissions

    def has_permission(self, required_permission: str) -> bool:
        # Permite acceso si el permiso está explícito, o si el usuario es Superadmin
        return (
            required_permission in self.permissions
            or "ROLE_SUPERUSER" or "ROLE_ADMIN" in self.roles
        )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUser:
    token = credentials.credentials
    try:
        # Decode the token supporting all standard HMAC strengths used by JJWT
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256", "HS384", "HS512"])
        
        username = payload.get("sub")
        tenant_id = payload.get("tenantId")
        tenant_slug = payload.get("tenantSlug")
        roles = payload.get("roles", [])
        
        if not username or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token no contiene información de usuario o inquilino requerida"
            )

        # Consultar los permisos asociados a los roles en la base de datos
        permissions = []
        if roles:
            try:
                # Obtenemos los nombres de los permisos para los roles del usuario
                query = text("""
                    SELECT DISTINCT p.name 
                    FROM permissions p
                    JOIN role_permission rp ON p.id = rp.permission_id
                    JOIN roles r ON r.id = rp.role_id
                    WHERE r.name IN :roles 
                      AND (r.tenant_id = :tenant_id OR r.tenant_id IS NULL)
                      AND r.is_active = true 
                      AND p.is_active = true
                """)
                # Convertimos roles a una tupla para la cláusula IN de SQL
                result = db.execute(query, {"roles": tuple(roles), "tenant_id": tenant_id})
                permissions = [row[0] for row in result.fetchall()]
            except Exception as e:
                print(f"Error fetching permissions for roles {roles}: {e}")
                # Fallback en caso de que ocurra algún error con la consulta o BD
                permissions = []
            
        return CurrentUser(
            username=username,
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            roles=roles,
            permissions=permissions
        )
    except jwt.ExpiredSignatureError as e:
        print(f"JWT Validation Error (Expired): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso ha expirado"
        )
    except jwt.InvalidTokenError as e:
        print(f"JWT Validation Error (Invalid): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido"
        )
    except Exception as e:
        print(f"JWT Validation Error (System): {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error validando token: {str(e)}"
        )

def require_permission(required_permission: str):
    def dependency(user: CurrentUser = Depends(get_current_user)):
        if not user.has_permission(required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: se requiere {required_permission}"
            )
        return user
    return dependency
