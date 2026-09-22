// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
import java.io.Writer;
import java.util.AbstractMap;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
/** Map compatibility required by the selected GeoServer consumers. */
// The inherited public Map contract is raw, matching selected importer source assignments.
@SuppressWarnings("rawtypes")
public final class JSONObject extends AbstractMap implements JSON {
    private final Map<Object,Object> properties = new LinkedHashMap<Object,Object>();
    private final boolean nullObject;
    public JSONObject() { this(false); }
    public JSONObject(boolean nullObject) { this.nullObject = nullObject; }
    public static JSONObject fromObject(Object value) {
        Object converted = value instanceof String ? JsonSupport.parse((String)value) : JsonSupport.normalize(value);
        if (converted == JSONNull.getInstance()) return new JSONObject(true);
        if (converted instanceof JSONObject) return (JSONObject)converted;
        throw new JSONException("Expected a JSON object");
    }
    void rawPut(String key, Object value) { properties.put(key, value); }
    public Object put(Object key, Object value) {
        if (nullObject) throw new JSONException("Cannot modify a null object");
        if (key == null) throw new JSONException("Object key is null");
        return properties.put(String.valueOf(key), JsonSupport.normalize(value));
    }
    public JSONObject element(String key, Object value) { put(key,value); return this; }
    public JSONObject element(String key, double value) { return element(key,Double.valueOf(value)); }
    public JSONObject element(String key, int value) { return element(key,Integer.valueOf(value)); }
    public JSONObject element(String key, long value) { return element(key,Long.valueOf(value)); }
    public JSONObject element(String key, boolean value) { return element(key,Boolean.valueOf(value)); }
    public JSONObject element(String key, Collection value) { return element(key,(Object)value); }
    public JSONObject element(String key, Map value) { return element(key,(Object)value); }
    public Object get(String key) { return properties.get(key); }
    public Object get(Object key) { return properties.get(key); }
    public Set<Map.Entry<Object,Object>> entrySet() { return properties.entrySet(); }
    public boolean containsKey(Object key) { return properties.containsKey(key); }
    public boolean has(String key) { return containsKey(key); }
    public Object remove(String key) { return properties.remove(key); }
    public JSONObject optJSONObject(String key) { Object value=get(key); return value instanceof JSONObject ? (JSONObject)value : null; }
    public Object remove(Object key) { return properties.remove(key); }
    public void clear() { properties.clear(); }
    public int size() { return properties.size(); }
    public boolean isEmpty() { return properties.isEmpty(); }
    public boolean isArray() { return false; }
    public boolean isNullObject() { return nullObject; }
    private Object required(String key) {
        if (!properties.containsKey(key)) throw new JSONException("Missing property: " + key);
        return properties.get(key);
    }
    public String getString(String key) { return String.valueOf(required(key)); }
    public boolean getBoolean(String key) { return JsonSupport.booleanValue(required(key)); }
    public double getDouble(String key) { return JsonSupport.number(required(key)).doubleValue(); }
    public int getInt(String key) { return JsonSupport.number(required(key)).intValue(); }
    public long getLong(String key) { return JsonSupport.number(required(key)).longValue(); }
    public JSONArray getJSONArray(String key) {
        Object value=required(key); if(value instanceof JSONArray) return (JSONArray)value;
        throw new JSONException("Not an array: " + key);
    }
    public JSONObject getJSONObject(String key) {
        Object value=required(key); if(value == JSONNull.getInstance()) return new JSONObject(true);
        if(value instanceof JSONObject) return (JSONObject)value;
        throw new JSONException("Not an object: " + key);
    }
    public Object opt(String key) { return get(key); }
    public String optString(String key) { return optString(key, ""); }
    public String optString(String key, String fallback) { Object value=get(key); return value == null ? fallback : String.valueOf(value); }
    public int optInt(String key, int fallback) { try { return getInt(key); } catch(JSONException e) { return fallback; } }
    public boolean optBoolean(String key, boolean fallback) { try { return getBoolean(key); } catch(JSONException e) { return fallback; } }
    public boolean equals(Object value) { return nullObject ? JSONNull.getInstance().equals(value) : super.equals(value); }
    public int hashCode() { return nullObject ? 0 : super.hashCode(); }
    public String toString() { return JsonSupport.text(this,0); }
    public String toString(int factor) { return JsonSupport.text(this,factor); }
    public String toString(int factor,int indent) { return JsonSupport.text(this,factor); }
    public Writer write(Writer writer) { return JsonSupport.write(this,writer,0); }
}
