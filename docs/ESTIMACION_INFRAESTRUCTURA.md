# Estimación de infraestructura y capacidad de PacheVideo

> Valores orientativos en USD por mes, sin impuestos, soporte ni variaciones regionales. Precios consultados el 17 de agosto de 2026. La capacidad real debe calibrarse con métricas de la beta.

## Qué determina el costo

El costo no crece principalmente por cuentas registradas. Crece por:

- Trabajos de video y audio procesados por día.
- Segundos promedio que cada trabajo ocupa un slot.
- CPU utilizada para transcodificar frente a solamente descargar/remultiplexar.
- Tamaño promedio descargado y entregado.
- Pico de solicitudes, no solamente promedio diario.
- Tiempo que conservamos los archivos.

Fórmulas de planificación:

```text
capacidad por hora = slots simultáneos × 3600 / segundos promedio por trabajo

slots requeridos = trabajos en la hora pico × segundos promedio / 3600

salida mensual en TB = trabajos por día × tamaño promedio en GB × 30 / 1000
```

## Supuestos del cálculo inicial

- Video promedio: 250 MB.
- Tiempo promedio: 6 minutos.
- Pico: cuatro veces el promedio horario.
- Un nodo de 8 vCPU ejecuta inicialmente cuatro slots simultáneos.
- Los archivos vencen después de una hora.
- Workers sin estado: no se guardan archivos permanentemente en sus discos.

Estos supuestos no son una promesa de capacidad. Calidad, codec, duración, fuente y restricciones externas pueden alterar mucho el resultado.

## Escenarios

| Escenario | Trabajos/día | Salida/mes | Slots para pico 4× | Presupuesto orientativo |
|---|---:|---:|---:|---:|
| Beta controlada | 100 | 0,75 TB | 2 | USD 75–120/mes |
| Lanzamiento | 1.000 | 7,5 TB | 17 | USD 700–1.100/mes |
| Viral | 10.000 | 75 TB | 167 | USD 6.000–10.000/mes |

### Beta controlada — hasta 100 trabajos por día

- 1 Droplet Basic de 4 vCPU, 8 GiB y 5 TB de transferencia: USD 48.
- PostgreSQL administrado de entrada: aproximadamente USD 15.
- Valkey/Redis administrado de entrada: USD 15; se puede alojar temporalmente en el VPS para reducir costo.
- Backup semanal del Droplet: aproximadamente 20% adicional.
- R2: normalmente dentro o cerca del nivel gratuito con retención de una hora.

Objetivo: medir tamaño, duración, errores y costo real. No comprar tráfico masivo todavía.

### Lanzamiento — hasta 1.000 trabajos por día

- 1 nodo de API/web de 4 vCPU y 8 GiB: USD 48.
- 5 workers de 8 vCPU y 16 GiB:
  - Basic compartido: 5 × USD 96 = USD 480.
  - CPU Optimized: 5 × USD 168 = USD 840.
- PostgreSQL administrado: USD 30–61.
- Valkey administrado: USD 30.
- Load balancer: alrededor de USD 12 si se utiliza el administrado.
- Backups y margen operativo: USD 100–150.
- R2 con una hora de retención: almacenamiento bajo; las operaciones probablemente quedan dentro del nivel gratuito inicial.

Recomendación: empezar con Basic y pasar workers calientes a CPU Optimized solo cuando las métricas demuestren saturación sostenida.

### Escenario viral — 10.000 trabajos por día

- Aproximadamente 167 slots para absorber un pico 4× con trabajos de seis minutos.
- Unas 42 máquinas de 8 vCPU si cada una mantiene cuatro slots.
- Solo la flota CPU Optimized sería aproximadamente USD 7.056 mensuales a precio publicado.
- API redundante, base de datos, cola, balanceador, monitoreo y margen llevan el rango razonable a USD 6.000–10.000, dependiendo de CPU compartida/dedicada y autoscaling.
- 75 TB mensuales de salida para archivos de 250 MB.

Este escenario no debe quedar encendido permanentemente desde el primer día. Los workers tienen que crecer y reducirse con la cola, con un máximo de gasto configurado.

## Arquitectura recomendada

```text
Landing / PWA / Windows
          |
     API sin estado
          |
  Auth + créditos + pagos ------ PostgreSQL
          |
  Cola Gratis / Cola Pro ------- Dead-letter queue
          |
  Workers FFmpeg escalables
          |
 Cloudflare R2 + URL firmada temporal
          |
       Usuario
```

Separaciones obligatorias:

- La web nunca ejecuta FFmpeg.
- La API no procesa archivos.
- Los workers pueden morir y reiniciarse sin perder el registro del trabajo.
- Los resultados no se sirven desde el disco del worker.
- La cola Pro tiene prioridad, pero mantiene límites por usuario.

## Transferencia y almacenamiento

DigitalOcean incluye transferencia saliente por Droplet y acumula el cupo a nivel de equipo. El excedente publicado es USD 0,01 por GiB. La carga del worker hacia un almacenamiento externo consume salida del Droplet.

Cloudflare R2 publica:

- USD 0,015 por GB-mes en almacenamiento Standard.
- Primeros 10 GB-mes, 1 millón de operaciones Class A y 10 millones Class B incluidos.
- Egreso directo desde R2 sin cargo.

Con archivos de una hora de vida, el costo de almacenamiento es pequeño. El gasto importante sigue siendo CPU, transferencia de los workers y abuso.

## Protección económica

- Gratis: un trabajo simultáneo y rate limit estricto.
- Pro: dos trabajos simultáneos y prioridad.
- Audio gratis, pero con límite de frecuencia, duración y tamaño.
- Máximo global de slots definido por presupuesto.
- Tiempo y tamaño máximo antes de iniciar la descarga completa.
- Cancelación automática de trabajos atascados.
- Alerta cuando el costo proyectado llegue al 50%, 75% y 90% del presupuesto.
- Interruptor para pausar trabajos Gratis sin afectar descargas ya terminadas.
- Allowlist de fuentes y bloqueo de automatizaciones.
- PacheVideo Desktop procesa localmente cuando sea posible, reduciendo el gasto de nube del usuario Pro.

## Fórmula de rentabilidad

```text
ingreso neto Pro = precio cobrado - comisión de pago - impuestos - reembolsos

clientes Pro de equilibrio =
  (servidores + almacenamiento + soporte + herramientas) / ingreso neto Pro
```

El precio en ARS debe poder modificarse desde administración y revisarse mensualmente. “Sin cupo mensual” siempre debe acompañarse de concurrencia limitada y política de uso razonable.

## Plan de compra recomendado

1. Contratar solamente la infraestructura Beta.
2. Incorporar 20–50 usuarios y medir durante siete días.
3. Calcular p50/p95 de segundos, MB y costo por trabajo.
4. Reemplazar los supuestos de este documento por datos reales.
5. Definir el precio final y el límite de adquisición diaria.
6. Escalar workers horizontalmente según la cola, nunca por intuición.

## Referencias oficiales

- [DigitalOcean Droplets](https://www.digitalocean.com/pricing/droplets)
- [DigitalOcean Managed Databases](https://www.digitalocean.com/pricing/managed-databases)
- [DigitalOcean bandwidth billing](https://docs.digitalocean.com/platform/billing/bandwidth/)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Cloudflare Queues pricing](https://developers.cloudflare.com/queues/platform/pricing/)
