from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Sanic, text, json
from sanic_ext import Extend, openapi
import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MONGO_URL, MONGO_DB, SERVER_HOST, SERVER_PORT, DEBUG

def create_app() -> Sanic:
    app = Sanic("blockchain_metrics")

    # Cấu hình Sanic Extensions với OpenAPI
    app.config.API_TITLE = "Blockchain Metrics API"
    app.config.API_VERSION = "1.0.0"
    app.config.API_DESCRIPTION = "API for blockchain metrics and analytics"
    app.config.OAS_UI_DEFAULT = "swagger"
    app.config.OAS_UI_REDOC = True
    app.config.RESPONSE_TIMEOUT = 300

    # Cấu hình CORS
    app.config.CORS_ORIGINS = "*"

    # Cấu hình Pydantic validation
    app.config.OAS_AUTODOC = True

    # Initialize Sanic Extensions
    Extend(app)

    # Add a root route for API health check and redirect to docs
    @app.route("/")
    async def index(request):
        return json({
            "status": "online",
            "api_name": "Blockchain Metrics API",
            "version": "1.0.0",
            "documentation": f"http://{SERVER_HOST}:{SERVER_PORT}/docs"
        })

    @app.listener('before_server_start')
    async def setup_db(app, loop):
        # Setup MongoDB connection
        app.ctx.mongo_client = AsyncIOMotorClient(MONGO_URL)
        app.ctx.db = app.ctx.mongo_client[MONGO_DB]

        # Create indexes for better performance
        await app.ctx.db.token_metrics.create_index("campaign_id")
        await app.ctx.db.campaign_reports.create_index("contract_address")
        await app.ctx.db.campaign_reports.create_index([("last_updated", -1)])

        print(f"Connected to MongoDB at {MONGO_URL}")

    @app.listener('after_server_stop')
    async def close_db(app, loop):
        # Close MongoDB connection
        app.ctx.mongo_client.close()
        print("Closed MongoDB connection")

    # Import and register blueprints
    from app.api.token_metrics import token_metrics_blueprint
    from app.api.etherscan import etherscan_blueprint

    app.blueprint(token_metrics_blueprint)
    app.blueprint(etherscan_blueprint)

    return app
