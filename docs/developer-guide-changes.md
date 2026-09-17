# Guia del desarrollador: como publicar cambios en ora-siebel-helm

Esta guia explica como trabajas cuando necesitas disparar una actualizacion de
Open Integration o subir archivos custom de Siebel Artifacts.

## Que puedes cambiar

| Path | Que podes hacer |
| --- | --- |
| `oidev2-WK66J3/siebel-openint-image-builder/Chart.yaml` | Solo incrementar `version:`. Es el trigger que hace que Flux reconstruya la imagen Open Integration. |
| `siebel-artifacts/Chart.yaml` | Solo incrementar `version:`. |
| `siebel-artifacts/build/mde/**` | Crear, modificar o borrar archivos (script, css, etc.). |

**Reglas obligatorias:**

- El autor del PR debe ser tu usuario (`@p-iabreit`).
- Un cambio en `build/mde/**` **siempre** debe ir acompanado del bump de
  `siebel-artifacts/Chart.yaml` en el mismo PR.
- El bump de versión debe ser un SemVer mayor que el actual (ej. `0.1.2` -> `0.1.3`).
- Para Open Integration, el PR debe tocar **únicamente** el `Chart.yaml` del
  image builder y **únicamente** la linea `version:`.

**Que NO podes tocar:** templates (`templates/**`), `values.yaml`, charts de
otros ambientes, otros charts (traefik, siebel, siebel-config, etc.),
`.github/` y cualquier otra ruta. El check de validacion los rechaza.

## Por que existe esto

GitHub no permite dar permiso de escritura por carpeta. Tenes `write` en todo el
repositorio, pero `main` esta protegido por un ruleset:

1. Todo cambio a `main` pasa por **Pull Request**.
2. El PR corre un check `validate-delegated-helm-change` que valida el alcance.
3. Se exige revision de un code owner (tu no podes aprobar tu propio PR).

## Flujo de trabajo

### Bump de Open Integration

```bash
git checkout main && git pull
git checkout -b bump-oi-wk66j3

# Editar solo la linea version en:
#   oidev2-WK66J3/siebel-openint-image-builder/Chart.yaml
#   version: 0.1.11  ->  version: 0.1.12

git add oidev2-WK66J3/siebel-openint-image-builder/Chart.yaml
git commit -m "Bump Open Integration image builder version"
git push origin bump-oi-wk66j3
```

Abrir el PR:

```bash
gh pr create --base main --head bump-oi-wk66j3 \
  --title "Bump Open Integration image builder version" \
  --body "Trigger incremental Open Integration build para oidev2-WK66J3."
```

### Siebel Artifacts: bump + archivos MDE

```bash
git checkout main && git pull
git checkout -b release-artifacts

# 1) Incrementar la version en siebel-artifacts/Chart.yaml
#    version: 0.1.2  ->  version: 0.1.3

# 2) Agregar/modificar/borrar archivos bajo siebel-artifacts/build/mde/**:
#    ej. siebel-artifacts/build/mde/applicationcontainer_external/.../ContactCardsPR.js

git add siebel-artifacts/Chart.yaml siebel-artifacts/build/mde/
git commit -m "Bump siebel-artifacts and update MDE custom files"
git push origin release-artifacts
```

Abrir el PR:

```bash
gh pr create --base main --head release-artifacts \
  --title "Bump siebel-artifacts with MDE updates" \
  --body "Actualizacion custom MDE + bump de version del chart."
```

> Si queres solo disparar el rebuild del chart sin cambios MDE, basta el bump de
> `siebel-artifacts/Chart.yaml` solo (caso #2 sin archivos MDE).

## Despues de abrir el PR

1. El check `validate-delegated-helm-change` se ejecuta solo.
2. Estado del check:
   - **Verde**: el cambio cumple el alcance. Queda a la espera del reviewer.
   - **Rojo**: el cambio no cumple las reglas. Corregirlo y hacer push a la misma
     rama (el check se vuelve a ejecutar).
3. Pedir aprobacion a un admin (`@ibreit-ar`). Sin su aprobacion el PR no se
   fusiona, aunque el check este verde.
4. Una vez aprobado, el admin fusiona. Con la fusion, Flux detecta el chart
   actualizado y dispara el incremental update.

## Errores comunes del check

| Error | Causa y solucion |
| --- | --- |
| `PR author 'X' is not authorized` | Abriste el PR con otra cuenta. Debe ser `@p-iabreit`. |
| `must change exactly one file: oidev2-.../Chart.yaml` | El PR toca mas de un archivo. Dejar solo el bump. |
| `may change only the 'version' field` | Cambiaste otra clave del Chart.yaml aparte de `version:`. |
| `must increase the SemVer 'version' field` | La version nueva no es mayor que la actual. |
| `Changes under siebel-artifacts/build/mde/ require a bump` | Cambiaste archivos MDE sin bump del chart en el mismo PR. |
| `Not allowed outside artifacts scope: [...]` | El PR toca rutas no permitidas (ej. templates, values.yaml, otros charts). |

## Consejos

- Siempre crear la rama desde `main` actualizado.
- Los cambios MDE deben estar listos antes de pedir el merge; al fusionar se
  dispara el rebuild.
- No borres archivos MDE que le hagan falta a otra version en curso; coordinarlo
  antes con el equipo.