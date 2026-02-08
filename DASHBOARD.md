# DVS Portal Dashboard Setup Guide

This guide will walk you through setting up the DVS Portal Dashboard in Home Assistant. The dashboard provides an overview of your parking reservations, balance, and related information.

![Example HACS dashboard](./example-dashboard.png)

## Prerequisites

- The DVS Portal integration is installed
- HACS is installed

---

## ⚠️ Upgrade note

If you are **upgrading from an older version** of this integration:

- Car sensors no longer use a custom `device_class`
- Auto-Entities filters must be updated to match on the attribute:
  - `dvs_entity: car`

See **Step 3** for the updated filters.

---

## Step 0: Install `auto-entities` Card through HACS

1. Navigate to **HACS** → **Frontend**
2. Search for `auto-entities`
3. Install it
4. Add the resource:

```yaml
resources:
  - url: /hacsfiles/lovelace-auto-entities/auto-entities.js
    type: module
```

---

## Step 1: Create `input_text` for License Plate

Navigate to **Settings** → **Helpers**

1. Click **ADD HELPER**
2. Choose **Text**
3. Name it e.g. `DVS License Plate`
4. Set entity ID to `input_text.dvsportal_license_plate`

---

## Step 2: Add Scripts

Add the following to `scripts.yaml`:

```yaml
dvsportal_parkingreservation_endofday:
  sequence:
    - service: dvsportal.create_reservation
      data_template:
        entity_id: "{{ entity_id }}"
        license_plate_value: "{{ license_plate_value }}"
        date_from: "{{ (now() + timedelta(minutes=1)).isoformat() }}"
        date_until: "{{ now().replace(hour=23, minute=59, second=59).isoformat() }}"

create_and_clear_reservation:
  sequence:
    - service: dvsportal.create_reservation
      data_template:
        date_from: "{{ (now() + timedelta(minutes=1)).isoformat() }}"
        date_until: "{{ now().replace(hour=23, minute=59, second=59).isoformat() }}"
        license_plate_value: "{{ states('input_text.dvsportal_license_plate') }}"
    - service: input_text.set_value
      target:
        entity_id: input_text.dvsportal_license_plate
      data:
        value: none
```

Reload scripts after adding them.

---

## Step 3: Create the Dashboard

1. Go to **Overview** → **Dashboards**
2. Click **+** → **Manual**
3. Paste the YAML below

### Dashboard YAML

```yaml
type: vertical-stack
title: DVS Portal Dashboard
cards:
  - type: entities
    title: General Info
    entities:
      - entity: sensor.guest_parking_balance
      - entity: sensor.reservations

  - type: custom:auto-entities
    card:
      type: glance
      title: Cars without Reservations
    filter:
      include:
        - domain: sensor
          attributes:
            dvs_entity: car
          state: not present
          options:
            tap_action:
              action: call-service
              service: script.dvsportal_parkingreservation_endofday
              service_data:
                entity_id: this.entity_id

  - type: custom:auto-entities
    card:
      type: glance
      title: Cars with Reservations
    filter:
      include:
        - domain: sensor
          attributes:
            dvs_entity: car
          state: /^(reserved|present)$/
          options:
            tap_action:
              action: call-service
              service: dvsportal.end_reservation
              service_data:
                entity_id: this.entity_id

  - type: entities
    title: New car
    entities:
      - entity: input_text.dvsportal_license_plate
      - entity: script.create_and_clear_reservation
```

4. Save the dashboard

You should now have a fully functional DVS Portal dashboard.
