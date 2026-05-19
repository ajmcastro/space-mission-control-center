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

    # Fog of War (V4)
    fog_of_war: bool = True          # set FOG_OF_WAR=false to reveal all terrain at start
    sensor_range: int = 2            # cells revealed in each direction from rover position

    # Fault Protection System (V4)
    fps_wheel_stuck_retry_limit: int = 2   # retries before attempting reverse
    fps_comm_loss_retry_limit: int = 2     # wait cycles before safe mode on comm loss
    fps_safe_mode_battery_pct: float = 10.0  # force safe mode when battery drops this low

    # Dynamic Terrain Events (V4)
    terrain_geyser_cycle_ticks: int = 15         # steps between geyser eruption/dormancy evaluations
    terrain_geyser_flip_prob: float = 0.35       # probability each geyser changes state per cycle
    terrain_fracture_prob_per_tick: float = 0.004  # probability crevasse spreads to adjacent cell each step
    terrain_frost_period_ticks: int = 20         # full day/night cycle length (night = half this)
    terrain_frost_cost_factor: float = 1.4       # movement cost multiplier during night frost

    # AEGIS Autonomous Target Selection (V4)
    aegis_max_auto_objectives: int = 10   # cap on self-generated objectives per mission run


settings = Settings()
