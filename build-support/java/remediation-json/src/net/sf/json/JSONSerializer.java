// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
/** Converts object or array values without loading classes from input. */
public final class JSONSerializer {
    private JSONSerializer() {}
    public static JSON toJSON(Object value) {
        Object converted = value instanceof String ? JsonSupport.parse((String)value) : JsonSupport.normalize(value);
        if (converted instanceof JSON) return (JSON)converted;
        throw new JSONException("Expected a JSON object, array or null");
    }
}
