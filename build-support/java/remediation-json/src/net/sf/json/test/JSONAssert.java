// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
package net.sf.json.test;
import net.sf.json.JSONObject;
/** Structural assertion used by selected source-owned REST tests. */
public final class JSONAssert {
    private JSONAssert() {}
    public static void assertEquals(String expected,JSONObject actual) {
        if(!JSONObject.fromObject(expected).equals(actual))throw new AssertionError("JSON structures differ");
    }
}
