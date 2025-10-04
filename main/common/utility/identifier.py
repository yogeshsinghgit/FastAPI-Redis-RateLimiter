from fastapi import Request


def get_identifier(request: Request):
    identifier = request.headers.get("X-User-Id")
    if not identifier:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            identifier = xff.split(",")[0].strip()
        else:
            client = request.client
            identifier = client.host if client else "Unknown"
            
    return identifier