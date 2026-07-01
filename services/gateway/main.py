import logging
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

# Route port mapping for microservices
SERVICES = {
    "store": "http://127.0.0.1:8001",
    "units": "http://127.0.0.1:8001",
    "kpi_records": "http://127.0.0.1:8001",
    "telegram": "http://127.0.0.1:8002",
    "templates": "http://127.0.0.1:8002",
    "kpis": "http://127.0.0.1:8003"
}

app = FastAPI(title="GIS API Gateway Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "GIS API Gateway is running.", "health": "/health", "status": "active"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "gateway"}

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def gateway_proxy(request: Request, path: str):
    """
    Dynamic catch-all proxy. Parses incoming request path and routes to the correct microservice.
    """
    parts = path.split("/")
    domain = parts[0] if parts else ""
    
    if domain not in SERVICES:
        logger.warning(f"Gateway received unmapped route: /api/{path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '/api/{path}' is not mapped in API Gateway."
        )

    target_base_url = SERVICES[domain]
    target_url = f"{target_base_url}/{path}"
    
    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)  # Exclude host header to prevent proxy validation failures
    
    query_params = dict(request.query_params)
    body = await request.body()

    logger.info(f"Gateway routing {method} /api/{path} -> {target_url}")

    try:
        async with httpx.AsyncClient() as client:
            res = await client.request(
                method=method,
                url=target_url,
                headers=headers,
                params=query_params,
                content=body,
                timeout=30.0
            )
            
            # Forward headers correctly
            response_headers = dict(res.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)
            
            return Response(
                content=res.content,
                status_code=res.status_code,
                headers=response_headers
            )
    except Exception as e:
        logger.error(f"Gateway proxy connection error to {target_url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gateway connection error: {e}"
        )
