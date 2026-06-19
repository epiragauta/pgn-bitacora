# Análisis de Fuentes de Datos — Bitácora PGN 2026-I
**Corte:** 31 de marzo de 2026  
**Fecha de análisis:** 19 de junio de 2026  
**Analista:** Edwin Piragauta / Claude Sonnet 4.6

---

## 1. Contexto

Se realizó el análisis exploratorio de los archivos Excel fuente para la elaboración de la **Bitácora PGN 2026-I** (primer corte de la vigencia 2026), con el fin de planificar la integración de estos datos en la aplicación web Bitácora PGN.

Directorio de fuentes: `D:\ws\Bases Bitácora\2026\Marzo\`

---

## 2. Estructura de Archivos Encontrados

La carpeta `Marzo\` contiene 8 subcarpetas que corresponden 1:1 con las secciones del dashboard, más un archivo adicional de SGP:

| # | Carpeta | Sección Dashboard | Archivo(s) disponible(s) |
|---|---|---|---|
| 1 | `1. INVERSIONES 2026 - PND 2022 - 2026` | Sec 1 – Transformaciones PND | ✅ `Inversiones 2026 - PND 2022-2026.xlsx` |
| 2 | `2. EVOLUCIÓN PRESUPUESTAL` | Sec 2 – Evolución histórica | ❌ Sin archivos |
| 3 | `3. REGIONALIZACIÓN` | Sec 3 – Mapa regional | ❌ Sin archivos |
| 4 | `4. EJECUCIÓN DE LA INVERSIÓN` | Sec 4 – Timeline histórico | ❌ Sin archivos |
| 5 | `5. VIGENCIAS FUTURAS` | Sec 5 – Vigencias futuras | ✅ `20260513 Nueva Base VF - Validada - Revisión Analistas.xlsx` |
| 6 | `6. EJECUCIÓN SECTORIAL` | Sec 6 – Tarjetas por sector | ❌ Sin archivos |
| 7 | `7. SDRT` | — | ❌ Sin archivos |
| 8 | `8. SCCI` | — | ❌ Sin archivos |
| — | Raíz `Marzo\` | — | `data 2022_2026_SGP.xlsx` (pendiente de analizar) |

**Conclusión:** Solo están disponibles los datos para las secciones 1 y 5. Las secciones 2, 3, 4 y 6 dependen de archivos que aún no han sido cargados en el directorio.

---

## 3. Archivo 1: Inversiones 2026 – PND 2022-2026

**Ruta:** `D:\ws\Bases Bitácora\2026\Marzo\1. INVERSIONES 2026 - PND 2022 - 2026\Inversiones 2026 - PND 2022-2026.xlsx`

### 3.1 Hojas del archivo

| Hoja | Tipo | Descripción |
|---|---|---|
| `Base` | Datos | Base transaccional: 1,366 proyectos × 26 columnas |
| `Alcance` | Descriptiva | Descripción del alcance de la información |
| `% part. por Transformación` | Pivot | Distribución % de inversión vigente por transformación PND |
| `% Distribución por componente` | Pivot | Distribución por transformación y componente (2025 vs 2026) |
| `Ejecución transformaciones` | Pivot | Apropiación vigente, C, O, P y % por transformación |
| `Clasificación programática` | Catálogo | Códigos y nombres del clasificador de gasto |
| `Asociación PND` | Mapeo | Tabla BPIN → Componente PND |

### 3.2 Estructura de la hoja Base

| Columna | Descripción | Tipo |
|---|---|---|
| `Concat` | Clave única concatenada | texto |
| `Sector` | Nombre del sector | texto |
| `Código` | Código del sector/entidad | texto |
| `Unidad Ejecutora` | Nombre de la entidad | texto |
| `BPIN` | Código del proyecto de inversión | texto |
| `Gsto`, `Prog`, `Subp`, `Proy`, `SubP2`, `SubOrd` | Clasificación programática | texto |
| `Rec` | Recurso | número |
| `Sit` | Situación de fondos (CSF/SSF) | texto |
| `Nombre` | Nombre del proyecto | texto |
| `Inicial` | Apropiación inicial | pesos COP |
| `Positivas` | Adiciones | pesos COP |
| `Negativas` | Reducciones | pesos COP |
| `Vigente` | Apropiación vigente | pesos COP |
| `CDP` | Certificado de Disponibilidad Presupuestal | pesos COP |
| `Compromisos` | Compromisos adquiridos | pesos COP |
| `Obligación` | Obligaciones | pesos COP |
| `Pago` | Pagos realizados | pesos COP |
| `FUENTE` | Fuente de financiación (Nacion/Propios) | texto |
| `Programa PGN` | Programa del PGN | texto |
| `Transformación` | Transformación del PND 2022-2026 | texto |
| `Componente` | Componente de la transformación PND | texto |

> **Unidades:** Todos los valores monetarios están en **pesos colombianos (COP)**. Para convertir a miles de millones (mmm, unidad usada en la app), dividir por **1,000,000,000**.

### 3.3 Totales agregados — Vigencia 2026 (Base completa)

| Concepto | Valor (mmm) | % s/Vigente |
|---|---|---|
| Apropiación vigente | 88,401.2 | 100.0% |
| Compromisos | 44,986.4 | 50.9% |
| Obligaciones | 9,962.1 | 11.3% |
| Pagos | 9,533.3 | 10.8% |

### 3.4 Distribución por Transformación PND

| # | Transformación | Vigente (mmm) | %Vigente | %C | %O | %P |
|---|---|---|---|---|---|---|
| 1 | Ordenamiento del territorio alrededor del agua y justicia ambiental | 2,638.9 | 3.0% | 43.3% | 7.3% | 6.8% |
| 2 | Seguridad humana y justicia social | 35,503.3 | 40.2% | 46.7% | 12.2% | 12.1% |
| 3 | Derecho humano a la alimentación | 1,803.1 | 2.0% | 55.9% | 5.3% | 4.4% |
| 4 | Transformación productiva, internacionalización y acción climática | 12,448.8 | 14.1% | 48.2% | 10.4% | 4.9% |
| 5 | Convergencia regional | 25,915.3 | 29.3% | 59.3% | 7.6% | 7.1% |
| 6 | Paz total e integral | 122.5 | 0.1% | 10.5% | 1.1% | 1.0% |
| 7 | Actores diferenciales para el cambio | 8,929.3 | 10.1% | 67.9% | 17.4% | 17.4% |
| 8 | Estabilidad macroeconómica | 1,040.1 | 1.2% | 68.7% | 6.3% | 6.2% |

> **Nota:** La hoja pivot "Ejecución transformaciones" reporta un total de 62,621 mmm, mientras que la agregación directa de la Base suma 88,401 mmm. La diferencia (~25,780 mmm) posiblemente corresponde a un filtro aplicado en la tabla dinámica (posiblemente excluye recursos propios u otros tipos). **Pendiente: verificar criterio del filtro antes de usar las tablas pivot directamente.**

### 3.5 Resumen por Sector (Sección 6)

| Sector | Vigente (mmm) | %C | %O | %P |
|---|---|---|---|---|
| Transporte | 15,555.4 | 62.5% | 8.3% | 7.8% |
| Inclusión Social y Reconciliación | 10,819.6 | 26.1% | 15.8% | 15.8% |
| Minas y Energía | 10,141.8 | 37.0% | 17.8% | 15.3% |
| Igualdad y Equidad | 9,418.0 | 63.5% | 18.8% | 18.8% |
| Educación | 6,820.3 | 62.4% | 9.8% | 9.7% |
| Trabajo | 6,782.2 | 37.3% | 10.4% | 10.4% |
| Hacienda | 4,839.9 | 78.2% | 11.5% | 11.5% |
| Defensa y Policía | 3,675.8 | 44.3% | 4.2% | 4.2% |
| Agricultura y Desarrollo Rural | 3,213.6 | 41.1% | 6.3% | 5.4% |
| Salud y Protección Social | 2,622.8 | 62.4% | 2.9% | 2.7% |
| Vivienda, Ciudad y Territorio | 2,578.3 | 74.4% | 4.9% | 4.7% |
| Tecnologías de la Información y las Comunicaciones | 1,707.9 | 69.7% | 16.8% | 15.4% |
| Rama Judicial | 1,449.6 | 16.2% | 1.1% | 1.1% |
| Ambiente y Desarrollo Sostenible | 1,114.3 | 47.6% | 5.5% | 5.5% |
| Planeación | 1,027.1 | 43.5% | 3.1% | 2.7% |
| Organismos de Control | 890.0 | 20.1% | 4.1% | 4.1% |
| Cultura | 739.3 | 50.3% | 5.1% | 3.8% |
| Justicia y del Derecho | 705.3 | 37.1% | 5.5% | 5.4% |
| Información Estadística | 522.4 | 53.3% | 10.6% | 10.6% |
| Ciencia, Tecnología e Innovación | 348.6 | 61.6% | 3.1% | 3.1% |
| Presidencia de la República | 324.9 | 30.4% | 6.1% | 6.1% |
| Sistema Integral de Verdad, Justicia, Reparación y no Repetición | 265.8 | 67.0% | 13.9% | 13.8% |
| Registraduría | 396.6 | 74.7% | 3.0% | 3.0% |
| Deporte y Recreación | 441.9 | 80.8% | 20.5% | 20.5% |
| Empleo Público | 411.9 | 45.2% | 7.8% | 7.5% |
| Interior | 423.0 | 31.1% | 1.8% | 1.5% |
| Fiscalía | 407.1 | 41.6% | 1.9% | 1.9% |
| Comercio, Industria y Turismo | 333.7 | 78.5% | 16.5% | 16.2% |
| Congreso de la República | 200.0 | 88.0% | 17.9% | 17.9% |
| Relaciones Exteriores | 201.1 | 29.1% | 7.9% | 7.5% |
| Inteligencia | 23.2 | 32.0% | 9.5% | 9.5% |

---

## 4. Archivo 5: Vigencias Futuras

**Ruta:** `D:\ws\Bases Bitácora\2026\Marzo\5. VIGENCIAS FUTURAS\20260513 Nueva Base VF - Validada - Revisión Analistas.xlsx`

### 4.1 Hojas del archivo

| Hoja | Descripción |
|---|---|
| `BASE_SIIF` | Base transaccional: 1,767 registros de VF |
| `TDBaseInflex` | Tabla dinámica base de inflexibilidades |
| `Detalle1` | Detalle adicional |
| `TD Cruce MGMP` | Cruce con Marco de Gasto de Mediano Plazo |
| `MGMP 2026-2029 Detalle` | Detalle MGMP por período |
| `BASE_SIIF (Transporte Program)` | Subconjunto de Transporte |
| `TD SECT` | Resumen por sector × fuente × año (2026-2054) |
| `TD SECT-ENT-PROY` | Resumen por sector, entidad y proyecto |
| `TD BITACORA` | **Resumen principal:** sector × año, todas las vigencias |
| `TD SECTORIAL` | Resumen sectorial simplificado |
| `TD Gráfica Petro` | Solo gobierno Petro, Fuente Nación |
| `TD Gráfica Santos-Duque` | Gobierno anterior |
| `TD Gobierno Comparado (Nuevo)` | Comparación entre gobiernos |
| `Conpes EGP %` | Porcentajes relacionados con Conpes |

### 4.2 Estructura de la hoja BASE_SIIF (columnas clave)

| Columna | Descripción |
|---|---|
| `Codigo_Sector` / `Nombre_Sector` | Sector |
| `Nombre_Unidad_Ejecutora` | Entidad |
| `BPIN` / `Nombre_Proyecto` | Proyecto |
| `Vigencia` | Año de la VF (2025-2054) |
| `Fuente` | Nación / Propios |
| `Tipo_VF` | Ordinaria / Excepcional, Nuevo / Adición |
| `Clasif_Gobierno` | Petro / Santos-Duque / anterior |
| `Valor_VF_Autorizada_SIIF` | Valor aprobado |
| `Valor_VF_Utilizada_SIIF` | Valor utilizado/comprometido |
| `Valor_VF_ACTUAL_SIIF` | Valor vigente actual |

> **Unidades:** Pesos COP. Dividir por 1e9 para mmm o 1e12 para billones.

### 4.3 Sectores con mayor VF 2026 (hoja TD BITACORA)

| Sector | VF 2026 (mmm aprox.) |
|---|---|
| Transporte | 11,954 |
| Defensa y Policía | 1,534 |
| Igualdad y Equidad | 6,010 |
| Hacienda | 3,809 |
| Salud y Protección Social | 1,230 |
| Vivienda, Ciudad y Territorio | 1,070 |

---

## 5. Brechas y Pendientes

| Pendiente | Descripción | Impacto |
|---|---|---|
| Verificar filtro pivot (Sec 1) | La hoja pivot suma 62,621 mmm vs 88,401 mmm en Base — identificar criterio | Alto |
| Archivos secciones 2, 3, 4, 6 | No están disponibles en la carpeta | Bloquea actualización completa de la app |
| `data 2022_2026_SGP.xlsx` | Archivo en raíz `Marzo\` sin analizar — posiblemente contiene SGP (Sistema General de Participaciones) | Medio |
| Constantes pesos 2025 | Sec 5 en la app usa precios constantes 2025; BASE_SIIF tiene valores corrientes — verificar deflactor | Alto |

---

## 6. Plan de Integración

Con los archivos disponibles, se puede construir el ETL para la Bitácora 2026-I que cargue:

1. **Metadatos** — nuevo registro `bitacora_id` (número=3 o siguiente, período=2026-I, corte=2026-03-31)
2. **Sección 1** — desde hoja `Ejecución transformaciones` y `% Distribución por componente` del Archivo 1
3. **Sección 6** — derivado de la hoja `Base` del Archivo 1, agregado por sector
4. **Sección 5** — desde hoja `TD BITACORA` o `TD SECT` del Archivo 5

Las secciones 2, 3 y 4 se dejarán con los datos de la bitácora anterior (fallback) hasta recibir los archivos faltantes.
