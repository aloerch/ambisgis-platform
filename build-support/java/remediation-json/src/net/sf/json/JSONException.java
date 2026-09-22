// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
/** Compatibility exception. Parser locations are retained in its diagnostic. */
public class JSONException extends RuntimeException {
    public JSONException(String message) { super(message); }
    public JSONException(Throwable cause) { super(cause); }
    public JSONException(String message, Throwable cause) { super(message, cause); }
}
