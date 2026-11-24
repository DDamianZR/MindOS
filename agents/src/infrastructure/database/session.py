from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

SessionFactory = async_sessionmaker[AsyncSession]


def create_session_factory(database_url: str) -> tuple[AsyncEngine, SessionFactory]:
    """
    Motor y fábrica de sesiones para los stores de Postgres del servicio de agentes.

    Los stores son de larga vida (los usa también el planificador de rutinas, fuera de una
    petición HTTP), así que cada operación abre su propia sesión corta y confirma al terminar,
    en vez de colgarse de una sesión por petición como hace Memory.
    """
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
