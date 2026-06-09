#!/bin/sh
set -eu
test -f apps/web-next-ts/src/lib/greeting.ts
grep -q "export function greeting" apps/web-next-ts/src/lib/greeting.ts
