using Microsoft.AspNetCore.StaticFiles;
using Microsoft.Extensions.FileProviders;
using PgnBitacora.Api.Data;
using PgnBitacora.Api.Endpoints;
using PgnBitacora.Api.Json;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<IDb, Db>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(o => o.SwaggerDoc("v1", new()
{
    Title = "API Bitácora PGN",
    Version = "3.0.0",
    Description = "Inversión pública Colombia 2022-2026 – DNP/DPIP",
}));

// El frontend lee claves snake_case exactas y distingue null de ausente:
// nada de política de nombres, y los nulos se escriben explícitamente.
builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = null;
    o.SerializerOptions.Converters.Add(new DecimalRecortadoConverter());
});

builder.Services.AddCors(o => o.AddDefaultPolicy(p =>
    p.AllowAnyOrigin().WithMethods("GET").AllowAnyHeader()));

var app = builder.Build();

app.UseCors();

if (app.Environment.IsDevelopment() || app.Configuration.GetValue("Swagger:Habilitado", true))
{
    app.UseSwagger();
    app.UseSwaggerUI(o => o.SwaggerEndpoint("/swagger/v1/swagger.json", "API Bitácora PGN v1"));
}

// Una bitácora inexistente responde 404, igual que el HTTPException del original.
app.Use(async (ctx, siguiente) =>
{
    try
    {
        await siguiente(ctx);
    }
    catch (BitacoraNoEncontradaException ex)
    {
        ctx.Response.StatusCode = StatusCodes.Status404NotFound;
        await ctx.Response.WriteAsJsonAsync(new { detail = ex.Message });
    }
});

app.MapGet("/health", () => Results.Ok(new { estado = "ok" })).ExcludeFromDescription();

app.MapMetadatos();
app.MapTransformaciones();
app.MapEvolucion();
app.MapRegionalizacion();
app.MapEjecucion();
app.MapVigenciasFuturas();
app.MapSectorial();
app.MapCredito();
app.MapSgp();
app.MapResumen();

// ── Archivos estáticos ────────────────────────────────────
// Equivale a los app.mount() de FastAPI: /data para los GeoJSON y la raíz
// para el frontend. Las rutas /api ya están mapeadas arriba y no chocan.
var raiz = RaizDelRepositorio(app.Environment.ContentRootPath, app.Configuration["Rutas:Raiz"]);
var dirFrontend = Path.Combine(raiz, "frontend");
var dirData = Path.Combine(raiz, "data");

// StaticFileMiddleware solo sirve extensiones con MIME conocido y .geojson
// no está en la tabla por defecto: sin esto, las capas del mapa Leaflet
// responden 404 y el mapa queda en blanco sin ningún error visible.
// StaticFiles de FastAPI servía cualquier archivo, así que se replica esa
// permisividad para no volver a perder un recurso en silencio.
var tiposContenido = new FileExtensionContentTypeProvider();
tiposContenido.Mappings[".geojson"] = "application/geo+json";

StaticFileOptions Opciones(string directorio, string rutaPeticion) => new()
{
    FileProvider = new PhysicalFileProvider(directorio),
    RequestPath = rutaPeticion,
    ContentTypeProvider = tiposContenido,
    ServeUnknownFileTypes = true,
    DefaultContentType = "application/octet-stream",
};

if (Directory.Exists(dirData))
{
    app.UseStaticFiles(Opciones(dirData, "/data"));
}

if (Directory.Exists(dirFrontend))
{
    app.UseDefaultFiles(new DefaultFilesOptions
    {
        FileProvider = new PhysicalFileProvider(dirFrontend),
        RequestPath = "",
    });
    app.UseStaticFiles(Opciones(dirFrontend, ""));
}
else
{
    app.Logger.LogWarning("No se encontró el directorio del frontend en {Ruta}", dirFrontend);
}

app.Run();

// Busca hacia arriba el directorio que contiene frontend/index.html, para
// que la API funcione igual ejecutada desde el proyecto (dotnet run) que
// desde el contenedor, donde todo cuelga de /app.
static string RaizDelRepositorio(string contentRoot, string? configurada)
{
    if (!string.IsNullOrWhiteSpace(configurada))
        return Path.GetFullPath(configurada);

    var dir = new DirectoryInfo(contentRoot);
    while (dir is not null)
    {
        if (File.Exists(Path.Combine(dir.FullName, "frontend", "index.html")))
            return dir.FullName;
        dir = dir.Parent;
    }
    return contentRoot;
}
