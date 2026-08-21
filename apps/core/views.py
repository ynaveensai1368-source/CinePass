from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """
    Production health check endpoint verifying database connectivity.
    GET /api/health/
    """
    db_status = "ok"
    try:
        connection.ensure_connection()
    except Exception:
        db_status = "error"

    status_code = 200 if db_status == "ok" else 500
    return JsonResponse({
        "status": "ok" if db_status == "ok" else "error",
        "database": db_status,
        "version": "1.0.0"
    }, status=status_code)
