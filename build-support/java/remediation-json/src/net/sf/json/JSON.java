// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
import java.io.Writer;
/** The value interface consumed by the selected GeoServer profile. */
public interface JSON {
    boolean isArray();
    boolean isEmpty();
    int size();
    String toString(int indentFactor);
    String toString(int indentFactor, int indent);
    Writer write(Writer writer);
}
