"""
F4.4 A2: Unified authentication dependency for admin endpoints.

Supports dual-mode auth:
- X-Admin-Secret header (for bots, automation, backward compat)
- JWT Bearer token (for SPA, web interface)

This resolves JWT↔API mismatch where SPA sends JWT but backend expects X-Admin-Secret.
"""
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from auth import get_current_employee, get_db
from models import Employee
from config import settings

# HTTP Bearer security (for JWT extraction)
security = HTTPBearer(auto_error=False)


async def get_current_admin(
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """
    Unified admin authentication dependency.
    
    Auth flow:
    1. If X-Admin-Secret header present and valid → admin access granted
    2. Otherwise → attempt JWT validation via get_current_employee
    3. If JWT valid AND user.role == 'admin' → admin access granted
    4. Otherwise → 401 Unauthorized or 403 Forbidden
    
    Returns:
        dict with keys:
        - role: str ("admin")
        - source: str ("secret" | "jwt")
        - id: int | None (employee_id if JWT, None if secret)
        - name: str | None (employee name if JWT, None if secret)
    
    Raises:
        HTTPException:
            - 401 if no valid auth provided
            - 403 if JWT valid but user not admin
    """
    # PATH 1: X-Admin-Secret validation (priority for backward compat)
    if x_admin_secret is not None:
        if (
            settings.INTERNAL_ADMIN_SECRET is not None
            and x_admin_secret == settings.INTERNAL_ADMIN_SECRET
        ):
            return {
                "role": "admin",
                "source": "secret",
                "id": None,
                "name": "System Admin (X-Admin-Secret)",
            }
        else:
            # Invalid X-Admin-Secret provided
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Admin-Secret header",
            )
    
    # PATH 2: JWT validation (for SPA)
    if credentials is None:
        # No X-Admin-Secret AND no JWT → unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (JWT or X-Admin-Secret)",
        )
    
    try:
        employee: Employee = await get_current_employee(credentials=credentials, db=db)
    except HTTPException as exc:
        # JWT missing, invalid, or expired → unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication required (JWT or X-Admin-Secret): {exc.detail}",
        ) from exc
    
    # JWT valid, check role
    if employee.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin role required (current role: {employee.role})",
        )
    
    # JWT valid + admin role
    return {
        "role": "admin",
        "source": "jwt",
        "id": employee.id,
        "name": employee.name,
    }
