from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "Enceladus Mission Control"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite+aiosqlite:///./mission_control.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_maxlen: int = 10_000
    use_redis: bool = False  # set USE_REDIS=true to activate RedisStreamBus

    # Simulation
    sim_step_delay_seconds: float = 0.5
    comm_delay_seconds: float = 2.5      # One-way light travel delay (Enceladus ~ 1.2B km)
    max_rovers_per_mission: int = 4

    # Grid world defaults
    default_grid_width: int = 20
    default_grid_height: int = 20

    # Rover defaults
    rover_battery_capacity: float = 1000.0
    rover_move_cost: float = 10.0
    rover_sample_cost: float = 25.0
    rover_comm_cost: float = 5.0

    # Event streams
    telemetry_stream: str = "telemetry"
    mission_stream: str = "missions"
    command_stream: str = "commands"
    anomaly_stream: str = "anomalies"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Claude API (V3)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 1024

    # RL Planner (V3)
    rl_episode_budget: int = 500
    rl_weight_target: float = 2.0
    rl_weight_terrain: float = 1.0
    rl_weight_geyser: float = 3.0

    # Physics (V3)
    physics_elevation_cost_factor: float = 0.5
    physics_thermal_anomaly_scale: float = 1.0


settings = Settings()
