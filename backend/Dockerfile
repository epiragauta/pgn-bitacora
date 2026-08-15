# ============================================================
# Bitácora de Inversión Pública — API .NET 8
#
# El contexto de build es la RAÍZ del repositorio, no backend/,
# porque la imagen también lleva el frontend y los GeoJSON:
#
#     docker build -f backend/Dockerfile -t dnp-dpip-bitacora .
#
# TLS lo termina Caddy en el host, así que aquí se sirve HTTP plano.
# ============================================================

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# El csproj se copia solo primero para que la capa de restore quede
# cacheada y no se rehaga con cada cambio de código.
COPY backend/PgnBitacora.sln ./
COPY backend/src/PgnBitacora.Api/PgnBitacora.Api.csproj src/PgnBitacora.Api/
RUN dotnet restore src/PgnBitacora.Api/PgnBitacora.Api.csproj

COPY backend/ ./
RUN dotnet publish src/PgnBitacora.Api/PgnBitacora.Api.csproj \
        -c Release -o /app/publish /p:UseAppHost=false


FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app

# curl solo para el HEALTHCHECK: la imagen aspnet no trae cliente HTTP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/publish ./

# Contenido estático que sirve la propia API, igual que hacía FastAPI.
# Program.cs busca hacia arriba el directorio con frontend/index.html y
# aquí lo encuentra en /app.
COPY frontend/ ./frontend/
COPY data/     ./data/

ENV ASPNETCORE_URLS=http://+:8080 \
    ASPNETCORE_ENVIRONMENT=Production \
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8080/health || exit 1

# Usuario sin privilegios provisto por la imagen base.
USER app

ENTRYPOINT ["dotnet", "PgnBitacora.Api.dll"]
