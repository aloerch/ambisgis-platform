// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
import java.io.Writer;
import java.util.AbstractList;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
/** List compatibility required by the selected GeoServer consumers. */
public final class JSONArray extends AbstractList<Object> implements JSON {
    private final List<Object> values = new ArrayList<Object>();
    public JSONArray() {}
    public static JSONArray fromObject(Object value) {
        Object converted=value instanceof String ? JsonSupport.parse((String)value) : JsonSupport.normalize(value);
        if(converted instanceof JSONArray) return (JSONArray)converted;
        JSONArray result=new JSONArray(); result.add(converted); return result;
    }
    public static Collection toCollection(JSONArray input,Class type) {
        Collection<Object> result=new ArrayList<Object>();
        for(Object value:input) {
            if(value==JSONNull.getInstance()) result.add(null);
            else if(type.isInstance(value)) result.add(value);
            else throw new JSONException("Array member is not assignable to requested type");
        }
        return result;
    }
    void rawAdd(Object value) { values.add(value); }
    public Object get(int index) { return values.get(index); }
    public int size() { return values.size(); }
    public boolean isEmpty() { return values.isEmpty(); }
    public boolean isArray() { return true; }
    public boolean add(Object value) { return values.add(JsonSupport.normalize(value)); }
    public void add(int index,Object value) { values.add(index,JsonSupport.normalize(value)); }
    public boolean addAll(Collection<? extends Object> additions) { boolean changed=false; for(Object value:additions) changed |= add(value); return changed; }
    public Object set(int index,Object value) { return values.set(index,JsonSupport.normalize(value)); }
    public Object remove(int index) { return values.remove(index); }
    public JSONArray element(Object value) { add(value); return this; }
    public String getString(int index) { return String.valueOf(get(index)); }
    public int getInt(int index) { return JsonSupport.number(get(index)).intValue(); }
    public long getLong(int index) { return JsonSupport.number(get(index)).longValue(); }
    public double getDouble(int index) { return JsonSupport.number(get(index)).doubleValue(); }
    public boolean getBoolean(int index) { return JsonSupport.booleanValue(get(index)); }
    public JSONObject getJSONObject(int index) { Object value=get(index); if(value instanceof JSONObject)return (JSONObject)value; if(value==JSONNull.getInstance())return new JSONObject(true); throw new JSONException("Not an object at index " + index); }
    public JSONArray getJSONArray(int index) { Object value=get(index); if(value instanceof JSONArray)return (JSONArray)value; throw new JSONException("Not an array at index " + index); }
    public String toString() { return JsonSupport.text(this,0); }
    public String toString(int factor) { return JsonSupport.text(this,factor); }
    public String toString(int factor,int indent) { return JsonSupport.text(this,factor); }
    public Writer write(Writer writer) { return JsonSupport.write(this,writer,0); }
}
