# Runbook: Configuracion de gobernanza de cambios delegados en ora-siebel-helm

Este runbook documenta como habilitar que un desarrollador (`@p-iabreit`) proponga
solo los cambios operativos necesarios para Open Integration y Siebel Artifacts,
sin acceso al resto del repositorio.

Se basa en tres piezas:

1. `.github/CODEOWNERS` — codeno ownership por directorio.
2. `.github/workflows/validate-delegated-helm-change.yaml` — chequeo obligatorio que
   valida el alcance del PR.
3. Un ruleset sobre `main` en GitHub — protege la rama y exige PR + review.

> Importante: GitHub no permite otorgar permisos de escritura por carpeta.
> El developer tiene `write` sobre todo el repo, pero el ruleset + el chequeo
> impiden que sus cambios fuera de alcance lleguen a `main`.

## Requisitos previos

- Acceso admin al repositorio `ibreit-ar/ora-siebel-helm`.
- `gh` autenticado como admin (`@ibreit-ar`).
- Conocer el usuario del developer (aqui `@p-iabreit`) y la identidad que usa
  Flux para hacer push a `main` (aqui `@ibreit-ar`).

## Alcance permitido al developer

| Path | Cambio permitido |
| --- | --- |
| `oidev2-WK66J3/siebel-openint-image-builder/Chart.yaml` | Incremento de `version:` (SemVer ascendente), solo esa clave. |
| `siebel-artifacts/Chart.yaml` | Incremento de `version:` (SemVer ascendente). |
| `siebel-artifacts/build/mde/**` | Crear, modificar o borrar archivos. Requiere bump de `siebel-artifacts/Chart.yaml` en el mismo PR. |
| Cualquier otra ruta | Rechazado por el chequeo. |

## Paso 1: Crear CODEOWNERS

Crear `.github/CODEOWNERS`:

```text
# Todo lo demas: solo admin
* @ibreit-ar

# Open Integration bump (solo oidev2-WK66J3)
/oidev2-WK66J3/siebel-openint-image-builder/Chart.yaml @p-iabreit @ibreit-ar

# Siebel Artifacts: Chart.yaml y arbol MDE
/siebel-artifacts/Chart.yaml @p-iabreit @ibreit-ar
/siebel-artifacts/build/mde/** @p-iabreit @ibreit-ar

# Politica solo admin
/.github/CODEOWNERS @ibreit-ar
/.github/workflows/** @ibreit-ar
```

## Paso 2: Crear el workflow de validacion

Crear `.github/workflows/validate-delegated-helm-change.yaml`:

```yaml
name: validate-delegated-helm-change

on:
  pull_request:
    branches:
      - main

permissions:
  contents: read
  pull-requests: read

jobs:
  validate-delegated-helm-change:
    name: Validate delegated Helm change
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Validate delegated change scope
        env:
          BASE_REF: ${{ github.event.pull_request.base.sha }}
          HEAD_REF: ${{ github.event.pull_request.head.sha }}
          AUTHOR: ${{ github.event.pull_request.user.login }}
        run: |
          python3 - <<'PY'
          import os
          import re
          import subprocess
          import sys

          base = os.environ["BASE_REF"]
          head = os.environ["HEAD_REF"]
          author = os.environ["AUTHOR"]

          allowed_author = "p-iabreit"
          oi_chart = "oidev2-WK66J3/siebel-openint-image-builder/Chart.yaml"
          artifacts_chart = "siebel-artifacts/Chart.yaml"
          mde_prefix = "siebel-artifacts/build/mde/"

          if author != allowed_author:
              print(f"::error::PR author '{author}' is not authorized. Only @{allowed_author} may submit these changes.")
              sys.exit(1)

          changed = subprocess.run(
              ["git", "diff", "--name-status", f"{base}...{head}"] if base != head else ["git", "diff", "--name-only", head],
              capture_output=True, text=True, check=True,
          ).stdout.splitlines()

          if not changed:
              print("::error::No file changes detected.")
              sys.exit(1)

          parsed = []
          for line in changed:
              if line.startswith(("A\t", "M\t", "D\t", "R\t", "C\t")):
                  status = line[0]
                  parts = line[2:].split("\t")
                  path = parts[1] if status == "R" else parts[0]
              else:
                  status = "M"
                  path = line
              parsed.append((status, path))

          print("Changed files:")
          for status, path in parsed:
              print(f"  {status} {path}")

          oi_changed = [p for s, p in parsed if p == oi_chart]
          oi_other = [p for s, p in parsed if p.startswith("oidev2-WK66J3/") and p != oi_chart]
          artifacts_changed = [p for s, p in parsed if p == artifacts_chart]
          mde_changed = [p for s, p in parsed if p.startswith(mde_prefix)]
          other = [p for s, p in parsed if p not in (oi_chart, artifacts_chart) and not p.startswith(mde_prefix) and not p.startswith("oidev2-WK66J3/")]

          def read_file(ref, path):
              out = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
              return out.stdout if out.returncode == 0 else None

          semver_re = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")

          def parse_semver(v):
              m = semver_re.match(v.strip())
              if not m:
                  return None
              return tuple(int(x) for x in m.group(1, 2, 3))

          def chart_bump_is_valid(path, base_ref, head_ref):
              base_content = read_file(base_ref, path)
              head_content = read_file(head_ref, path)
              if base_content is None or head_content is None:
                  return False
              base_match = re.search(r"^version:\s*(.+)$", base_content, re.M)
              head_match = re.search(r"^version:\s*(.+)$", head_content, re.M)
              if not base_match or not head_match:
                  return False
              base_version = parse_semver(base_match.group(1))
              head_version = parse_semver(head_match.group(1))
              if not base_version or not head_version:
                  return False
              return head_version > base_version

          def chart_diff_only_version(path, base_ref, head_ref):
              base_lines = read_file(base_ref, path).splitlines()
              head_lines = read_file(head_ref, path).splitlines()
              diff_lines = [
                  line for line in subprocess.run(
                      ["git", "diff", f"{base_ref}...{head_ref}", "--", path],
                      capture_output=True, text=True, check=True,
                  ).stdout.splitlines()
              ]
              changed_keys = set()
              for line in diff_lines:
                  if line.startswith("+") and not line.startswith("+++") or line.startswith("-") and not line.startswith("---"):
                      m = re.match(r"^[+-]\s*([A-Za-z0-9_]+):", line)
                      if m:
                          changed_keys.add(m.group(1))
              return changed_keys == {"version"}

          ok = True

          if oi_changed or oi_other:
              if len(changed) != 1 or not oi_changed:
                  print(f"::error::Open Integration PR must change exactly one file: {oi_chart}")
                  ok = False
              else:
                  if oi_other:
                      print(f"::error::Unexpected oidev2-WK66J3 changes: {oi_other}")
                      ok = False
                  if not chart_bump_is_valid(oi_chart, base, head):
                      print(f"::error::{oi_chart} must increase the SemVer 'version' field.")
                      ok = False
                  if not chart_diff_only_version(oi_chart, base, head):
                      print(f"::error::{oi_chart} may change only the 'version' field.")
                      ok = False
          elif artifacts_changed or mde_changed:
              if not artifacts_changed:
                  print(f"::error::Changes under {mde_prefix} require a bump of {artifacts_chart} in the same PR.")
                  ok = False
              if not chart_bump_is_valid(artifacts_chart, base, head):
                  print(f"::error::{artifacts_chart} must increase the SemVer 'version' field.")
                  ok = False
              if other:
                  print(f"::error::Not allowed outside artifacts scope: {other}")
                  ok = False
          else:
              print(f"::error::No allowed change matches this PR.")
              ok = False

          if not ok:
              sys.exit(1)

          print("Validation passed: change is limited to the delegated scope.")
          PY
```

> Nota: el job se llama `validate-delegated-helm-change` (no `validate-scope`) porque
> GitHub usa el nombre del job como nombre del status check. El ruleset referencia
> exactamente `validate-delegated-helm-change`.

## Paso 3: Publicar CODEOWNERS y el workflow

```bash
git add .github/CODEOWNERS .github/workflows/validate-delegated-helm-change.yaml
git commit -m "Add delegated Helm change governance"
git push origin main
```

## Paso 4: Dar acceso `write` al developer

```bash
gh api -X PUT repos/ibreit-ar/ora-siebel-helm/collaborators/p-iabreit -f permission=write
```

## Paso 5: Crear el ruleset sobre main

Crear `ruleset.json`:

```json
{
  "name": "main-delegated-helm-governance",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["refs/heads/main"], "exclude": [] }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": true,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [ { "context": "validate-delegated-helm-change" } ]
      }
    },
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ],
  "bypass_actors": []
}
```

Aplicarlo:

```bash
gh api --method POST repos/ibreit-ar/ora-siebel-helm/rulesets --input ruleset.json
```

> El tipo correcto para status checks en rulesets es `required_status_checks`
> con `required_status_checks` (array), **no** `contexts`.

## Paso 6: Bypass del push automatico de Flux

El chart `siebel-artifacts` genera un `ImageUpdateAutomation` que hace push
directo a `main` de este repositorio (rama `main`, path `./siebel-artifacts`).
Con el ruleset activo ese push queda bloqueado salvo que el actor este en la
lista de bypass. Obtener el usuario que usa Flux (aqui `@ibreit-ar`):

```bash
gh api users/ibreit-ar -q '.id'
```

Registrarlo como bypass actor sobre el ruleset:

```bash
cat ruleset.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
d['bypass_actors'] = [{'actor_id': <ID>, 'actor_type': 'User', 'bypass_mode': 'always'}]
json.dump(d, open('ruleset.json', 'w'), indent=2)
"
gh api -X PUT repos/ibreit-ar/ora-siebel-helm/rulesets/<RULESET_ID> --input ruleset.json
```

`<RULESET_ID>` se obtiene con:

```bash
gh api repos/ibreit-ar/ora-siebel-helm/rulesets -q '.[] | [.id, .name] | @tsv'
```

## Verificacion

```bash
# Colaborador con write
gh api repos/ibreit-ar/ora-siebel-helm/collaborators -q '.[] | [.login, .role_name] | @tsv'

# Ruleset activo
gh api repos/ibreit-ar/ora-siebel-helm/rulesets -q '.[] | [.name, .enforcement] | @tsv'

# CODEOWNERS publicado
gh api repos/ibreit-ar/ora-siebel-helm/contents/.github/CODEOWNERS -q '.content' | base64 -d
```

Para una prueba end-to-end, abrir un PR real (ej. bump de version en
`oidev2-WK66J3/.../Chart.yaml`) como el developer autorizado y confirmar que el
check `validate-delegated-helm-change` pasa en verde; y abrir un PR con un cambio
fuera de alcance y confirmar que el check falla.

## Solucion de problemas

- `Invalid property /rules/N`: el regla no coincide con el esquema del ruleset.
  Validar con los nombres exactos de la API (`pull_request`,
  `required_status_checks`, `deletion`, `non_fast_forward`).
- El check nunca aparece en el PR: confirmar que el workflow existe en `main`
  (no solo en ramas) y que el job se llama igual que el contexto requerido.
- Flux no puede empujar a `main`: revisar que la identidad de Flux este en
  `bypass_actors` del ruleset.
- Push directo del admin rechazado: el admin tambien esta sujeto al ruleset;
  solo pasa si figura como bypass actor o por UI desde la rama protegida.