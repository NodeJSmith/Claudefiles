# TypeScript

## No `any`

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not use `any`. It disables type checking for everything it touches. Use `unknown` for external data and narrow before use.

```ts
// bad
function handle(input: any) {
  return input.foo.bar;
}

// good
function handle(input: unknown) {
  if (typeof input === "object" && input !== null && "foo" in input) {
    // narrowed; compiler verifies access
  }
}
```

External sources include RPC payloads, `JSON.parse`, `postMessage`, IPC, file contents, environment variables, and database results.

## No `as` Casts

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Every `as` is a potential runtime crash. Cast only after the type system has verified the claim through validation. The canonical valid use is branded type constructors, where the `as` is earned because the preceding validation is the only way to create the type.

```ts
// bad
const user = data as User;

// good: earned cast after full validation
function parseUser(data: unknown): User {
  const parsed = UserSchema.parse(data);
  return parsed;
}
```

When refactoring an `as` out of existing code, identify why TypeScript cannot infer:
- Missing discriminant: add one, switch to a discriminated union
- Overly wide source type: narrow it
- Untyped boundary: add a parse function or schema
- Genuinely inexpressible: use a branded type or `satisfies`

## Discriminated Unions Over Optional Fields

If a bug forces the question "can this combination actually happen?", the type is too loose. Model variants with a literal discriminant.

```ts
// bad: boolean + optionals lets contradictory states exist
type DiffState = { loading: boolean; diff?: GitDiff; error?: string };

// good: only valid states exist
type DiffState =
  | { kind: "loading" }
  | { kind: "ready"; diff: GitDiff }
  | { kind: "error"; error: string };
```

Pick one discriminant name (`kind`, `type`, `tag`) per codebase and stick to it.

A subtle anti-pattern worth naming: `{ completed: boolean; completedAt?: Date }` admits `completed: true; completedAt: undefined`. Derive the boolean from a single source like `completedAt !== null`, or model the variants explicitly.

## Branded Types

Brand primitives so they cannot be mixed up. Validate once at creation; trust the type downstream.

```ts
type UserId = string & { readonly __brand: "UserId" };
type OrderId = string & { readonly __brand: "OrderId" };

function parseUserId(input: string): UserId {
  if (!isUUID(input)) throw new Error(`Invalid user id: ${input}`);
  return input as UserId;
}
```

Use the `readonly __brand: "X"` convention consistently.

## Exhaustive Matching

In default arms, assign the discriminant to a `never`-typed local. The compiler errors if a new variant is added without handling.

```ts
function area(s: Shape): number {
  switch (s.kind) {
    case "circle":
      return Math.PI * s.radius ** 2;
    case "rect":
      return s.width * s.height;
    default: {
      const _exhaustive: never = s;
      return _exhaustive;
    }
  }
}
```

## Narrowing Hierarchy

From best to last-resort:

1. Discriminant switch/if (compiler narrows automatically)
2. `in` operator (`"key" in obj` narrows to variants containing that key)
3. `typeof` / `instanceof`
4. User-defined type guard (must actually verify the claim)
5. `as` cast (only after validation)

## `satisfies` Over `as`

`satisfies` validates without widening literal types.

```ts
// bad: widens, loses literal types
const config = { theme: "dark", cols: 3 } as Config;

// good: validates AND preserves literal types
const config = { theme: "dark", cols: 3 } satisfies Config;
// config.theme is "dark" (literal), not string
```

## Schema-Derived Types

When a proto, OpenAPI spec, GraphQL schema, or database migration defines a shape, derive from the generated types instead of duplicating them. Manual duplication drifts.

Reach for `Pick`, `Omit`, `Parameters`, `ReturnType`, `Awaited`, `typeof` before declaring a new interface.

```ts
// bad: duplicate shape that drifts
type CheckSummary = {
  totalCount: number;
  checks: { name: string; status: string }[];
};

// good: derive from the generated type
import type { ChecksMessage } from "<generated module>";
function renderChecks(s: Pick<ChecksMessage, "totalCount" | "checks">) { ... }
```

## Object Arguments Over Positional

Pass objects when a function has 3+ parameters of the same type. Order-independent and self-documenting.

```ts
// bad: swap two args, still compiles
openFile(uri, startLine, startCol, endLine, endCol);

// good
openFile({ uri, selection: { startLine: 10, startCol: 1, endLine: 10, endCol: 1 } });
```

Skip on hot paths where the allocation cost matters (per-frame render, tokenizers, parsers).

## Boundary Validation

Follow `references/common/security.md` (input validation at boundaries). TypeScript-specific addenda:

- Wire formats (proto, JSON-RPC): parse with `ignoreUnknownFields` for forward compatibility.
- Persisted JSON: versioned blob with try/catch around the parse.
- Do not re-validate deep in call chains. If the boundary validated it, the type carries the proof.

## Strict Mode

All TypeScript projects must use strict mode (`"strict": true` in tsconfig). Do not selectively disable strict checks (`strictNullChecks`, `noImplicitAny`, etc.).

## `interface` vs `type`

Use `interface` when a shape is intended to be extended (plugin APIs, base configs). Use `type` for unions, intersections, and computed shapes. For plain closed shapes, either is fine. Pick one per project and stay consistent.

```ts
// interface for extensible shapes
interface PluginConfig {
  name: string;
  version: string;
}

// type for unions and utilities
type Result = Success | Failure;
type UserKeys = keyof User;
```

## No Enums

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not use TypeScript `enum`. Use `as const` objects or union types instead. Enums have runtime behavior that surprises, don't tree-shake well, and have numeric/string confusion.

```ts
// bad
enum Status { Active, Inactive }

// good
const Status = { Active: "active", Inactive: "inactive" } as const;
type Status = (typeof Status)[keyof typeof Status];
```

## Null Handling

Use `null` for intentional absence and `undefined` for unset/optional. Do not mix them for the same concept within a codebase. Prefer nullish coalescing (`??`) and optional chaining (`?.`) over manual checks.

```ts
// good
const name = user.displayName ?? user.username ?? "Anonymous";
const city = user.address?.city;
```
