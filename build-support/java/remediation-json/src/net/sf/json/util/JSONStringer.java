// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json.util;
import java.io.StringWriter;
/** In-memory instance of the independently authored streaming writer. */
public class JSONStringer extends JSONBuilder {
    public JSONStringer(){super(new StringWriter());}
    public String toString(){return complete ? writer.toString() : null;}
}
