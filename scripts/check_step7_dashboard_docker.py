from pathlib import Path

root = Path(__file__).resolve().parents[1]
dockerfile = root / "dashboard" / "Dockerfile"
public_dir = root / "dashboard" / "public"
tsconfig = root / "dashboard" / "tsconfig.json"

errors = []
text = dockerfile.read_text(encoding="utf-8") if dockerfile.exists() else ""
if "RUN mkdir -p public && npm run build" not in text:
    errors.append("dashboard/Dockerfile must create public before next build")
if "COPY --from=builder --chown=nextjs:nodejs /app/public ./public" not in text:
    errors.append("dashboard/Dockerfile must copy public from builder")
if not public_dir.exists():
    errors.append("dashboard/public directory is missing")
if tsconfig.exists() and '.next/dev/types/**/*.ts' not in tsconfig.read_text(encoding="utf-8"):
    errors.append("dashboard/tsconfig.json is missing Next.js dev type include")

if errors:
    print("[ERROR] STEP 7.1 dashboard Docker preflight")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("[OK] STEP 7.1 dashboard Docker preflight")
print("  public_dir=present")
print("  dockerfile_public_guard=present")
print("  next_dev_types_include=present")
