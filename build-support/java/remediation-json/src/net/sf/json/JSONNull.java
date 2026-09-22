// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
import java.io.Writer;
/** Singleton representing an explicit JSON null. */
public final class JSONNull implements JSON {
    private static final JSONNull INSTANCE = new JSONNull();
    private JSONNull() {}
    public static JSONNull getInstance() { return INSTANCE; }
    public boolean equals(Object value) { return value == null || value == this || value instanceof JSONObject && ((JSONObject)value).isNullObject(); }
    public int hashCode() { return 0; }
    public String toString() { return "null"; }
    public String toString(int factor) { return toString(); }
    public String toString(int factor, int indent) { return toString(); }
    public boolean isArray() { return false; }
    public boolean isEmpty() { return true; }
    public int size() { return 0; }
    public Writer write(Writer writer) { return JsonSupport.write(this, writer, 0); }
}
