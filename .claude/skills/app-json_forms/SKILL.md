---
name: app-json_forms
description: Build IAP JSON Forms — static-enum dropdowns, REST-bound dropdowns (live data pulled from IAP endpoints), and cascading dropdowns (aka field dependency — one field's value drives another's URL path param). Use when creating, updating, or wiring forms consumed by manual triggers, manual tasks (ShowJsonForm), or any UI surface that needs a structured input panel.
argument-hint: "[form name or operation]"
---

# JSON Forms (app-json_forms)

JSON Forms are reusable form definitions stored in the `json-forms` application. They drive structured input panels across IAP — manual triggers in Operations Manager, the `JsonForms/ShowJsonForm` manual task, and any workflow surface that prompts a user for typed input.

A form is a single document with four cooperating schemas — `struct` (UI rendering), `schema` (data contract / validation), `uiSchema` (per-field widget hints), and `bindingSchema` (live-data binding for REST dropdowns). Get the relationships wrong and the form will render but break silently at runtime.

## Concepts

- **`struct`** — the UI definition. `struct.type` is always `"array"`; `struct.items[]` is the list of fields. `customKey` on each field becomes the property key in `schema` and the variable key when the form's data is consumed.
- **`schema`** — the data contract. `schema.properties.<customKey>` must exist for every field in `struct.items[]` (and stay in sync with the field's type, enum values, etc.). `schema.required` lists mandatory `customKey`s.
- **`uiSchema`** — per-`customKey` widget hints: placeholder text, `ui:widget` overrides, disabled flags. Required for cascading dropdowns (see below).
- **`bindingSchema`** — empty `{}` for static-enum forms. Required (and non-trivial) for REST-bound dropdowns: every REST-bound field needs a mirroring `bindingSchema.properties.<customKey>` entry. Studio fills this in invisibly through the GUI; the server does not.
- **Static vs. REST-bound dropdowns** — static dropdowns hardcode the list via `enum`/`enumNames`. REST-bound dropdowns pull options live from an IAP endpoint at form-render time.
- **Cascading dropdowns** (aka **field dependency** in the Studio UI) — a REST-bound dropdown whose URL path parameter is filled from another field's current value. The dependent field re-fetches when the source field changes.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/json-forms/forms` | List all JSON forms |
| GET | `/json-forms/forms/{id}` | Fetch a single form |
| POST | `/json-forms/forms` | Create a JSON form |
| PUT | `/json-forms/forms/{id}` | Update a JSON form (full replacement — see Update below) |
| DELETE | `/json-forms/forms` | Bulk delete — body `{"ids":["...","..."]}`. There is no per-id DELETE endpoint; per-id calls 404. |
| GET | `/automation-studio/json-forms/method-options` | Canonical list of bindable endpoints (same list Studio shows in its dropdown picker) |

## Create a JSON Form

```
POST /json-forms/forms
```

Choose the helper that matches your form's dropdown needs:

| Use case | Helper |
|---|---|
| Static-enum dropdowns only (hardcoded option lists) | `${CLAUDE_PLUGIN_ROOT}/helpers/create-json-form.json` |
| REST-bound or cascading dropdowns (live data from IAP endpoints) | `${CLAUDE_PLUGIN_ROOT}/helpers/create-json-form-rest-bound.json` |

Both helpers are annotated scaffolds — read the `_comment_*` fields inline before customizing.

### Static-enum dropdowns

`enum`/`enumNames` arrays appear in both `struct.items[i]` and `schema.properties.<customKey>` — they must stay in sync.

- `struct.items[i].enum` / `enumNames` are arrays of `{id, label, value}` objects.
- `schema.properties.<customKey>.enum` / `enumNames` are **flat string arrays** of the same values (not objects).

Leave `bindingSchema: {}` for static-enum forms.

### REST-bound dropdowns

When options should reflect live platform state (devices, inventories, projects, templates) instead of a hardcoded list, the dropdown pulls from a GET against an IAP endpoint at render time. Three things must line up:

1. **`struct.type` MUST be `"array"`** (not `"object"`). The static-enum scaffold uses `"array"` too — keep it.
2. **`bindingSchema.properties.<customKey>` must mirror every REST-bound field.** Studio reverse-engineers `bindingSchema` from `struct` in the GUI, but the server does not — leaving `bindingSchema: {}` produces dropdowns that render but never fetch.
3. **Endpoint discovery:** `GET /automation-studio/json-forms/method-options` returns the canonical list of bindable endpoints — the same list Studio shows in its dropdown picker.

Per-field shape in `struct.items[i]`:

```jsonc
{
  "type": "string",
  "title": "Site",
  "binding": true,
  "rel": "collection",
  "targetPointer": "/enum",
  "method": "GET",
  "base": "/inventory_manager",
  "href": "/v1/inventories",
  "sourcePointer": "/result/data",
  "sourceKeyPointer": "/name",
  "customKey": "site"
}
```

- `base + href` is the endpoint.
- `sourcePointer` is a JSON pointer into the response, walked to the array of items.
- `sourceKeyPointer` is the per-item field that becomes BOTH the value and the label. **`labelKeyPointer` is unused** — both columns come from `sourceKeyPointer`.

### Cascading dropdowns (aka field dependency)

The Studio UI labels this pattern **field dependency**; the form JSON calls it cascading. Same feature, two names. A REST-bound dropdown whose URL path parameter is filled from another field's value (e.g., dropdown 2 lists devices from the inventory selected in dropdown 1):

- The dependent dropdown's `href` stays as a **TEMPLATE** with placeholders: `/v1/inventories/:inventoryIdentifier/nodes`. **Path params use `:name` colon syntax, NOT `{name}` curly braces.**
- A `variables` array maps each placeholder to a JSON pointer into form data: `[{"name": "inventoryIdentifier", "reference": "/site"}]` substitutes `:inventoryIdentifier` with whatever value the field whose `customKey` is `site` currently holds.
- The same `variables` array must appear in **both** places:
  - `struct.items[i].variables`
  - `bindingSchema.properties.<dependentKey>.binding:hyperSchema.links[0].variables`
- **Both the source and the dependent field need `ui:widget: "DependencyWidget"`** in `uiSchema` — without it, the runtime will not re-fetch when the source changes.

## Update a JSON Form

```
PUT /json-forms/forms/{id}
```

- Body MUST be wrapped in `{"options": {...}}`.
- Include ALL fields the form already has: `created`, `createdBy`, `lastUpdated`, `lastUpdatedBy`, `name`, `description`, `struct`, `schema`, `uiSchema`, `validationSchema`, `bindingSchema`, `version`.
- This is a **full replacement** — omitting any field clears it.

## Delete JSON Forms

Bulk-only:

```
DELETE /json-forms/forms
Body: {"ids": ["<id1>", "<id2>", ...]}
```

Per-id calls (`DELETE /json-forms/forms/<id>`) return 404 — the endpoint does not exist.

## Wiring to a Manual Trigger

A JSON Form is consumed by an Operations Manager **manual trigger** that hands the user's form input to a workflow as job variables. See `builder-agent` for the trigger creation details.

**Critical flag — `legacyWrapper: false`:** The default is `true`, which wraps form field values under a `formData` object and breaks the mapping to workflow job variables. Set `legacyWrapper: false` so each form field maps directly to a workflow input variable by name (i.e., field `customKey: "device_name"` → job variable `device_name`).

Required trigger fields: `name`, `type` (`"manual"`), `enabled`, `actionType` (`"automations"`), `actionId`, `formId`, `legacyWrapper`.

Helper for the wired-up trigger: `${CLAUDE_PLUGIN_ROOT}/helpers/create-ops-manager-trigger-manual.json`.

## Common Gotchas

- **`struct.type` is `"array"`, not `"object"`.** Forms with `"object"` render empty.
- **`bindingSchema` mirroring is mandatory for REST-bound fields.** Studio hides this in the GUI; an API-created form needs both `struct.items[i]` AND `bindingSchema.properties.<customKey>` populated, or the dropdown renders and never fetches.
- **`:name` colon syntax in `href`, not `{name}`.** Curly-brace placeholders are silently ignored.
- **`enum`/`enumNames` flat-vs-object asymmetry.** In `struct.items[i]` they're `{id, label, value}` objects; in `schema.properties.<customKey>` they're flat string arrays.
- **`DependencyWidget` required on BOTH ends of a cascade.** Easy to remember to set it on the dependent field and forget the source — without the source-side widget the dependent won't re-fetch.
- **`labelKeyPointer` is a red herring.** Don't bother setting it; both label and value come from `sourceKeyPointer`.
- **Bulk DELETE has no per-id alternative.** Always send `{"ids":[...]}` to `/json-forms/forms`.

## See Also

- `builder-agent` for workflows that consume form output, manual-trigger wiring, and project-level component management.
- Helper files in `${CLAUDE_PLUGIN_ROOT}/helpers/`:
  - `create-json-form.json` — static-enum scaffold
  - `create-json-form-rest-bound.json` — REST-bound + cascading scaffold (Inventory Manager Site/Device cascade worked example)
  - `create-ops-manager-trigger-manual.json` — manual trigger that consumes a form
