# Platform enforcement acceptance — 2026-09-17

- Protected branch: `main`
- Required checks: `fast-path-start-gate`, `gate-contract`
- Strict status checks: enabled
- Admin enforcement: enabled
- Force pushes: disabled
- Branch deletion: disabled
- Direct-write RED probe commit: `a0f6781402d03c503c5828238a56969943d7c545`
- RED result: rejected with HTTP 422 because 2 required checks were expected.
- This file is the GREEN-path evidence payload and must enter `main` only through a pull request with both required checks successful.
