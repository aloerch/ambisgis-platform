// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json;
import com.fasterxml.jackson.core.*;
import com.fasterxml.jackson.core.json.JsonReadFeature;
import com.fasterxml.jackson.core.util.DefaultIndenter;
import com.fasterxml.jackson.core.util.DefaultPrettyPrinter;
import java.beans.Introspector;
import java.beans.PropertyDescriptor;
import java.io.IOException;
import java.io.StringWriter;
import java.io.Writer;
import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.Map;
/** Independently authored conversion; Jackson supplies JSON tokenization and quoting. */
public final class JsonSupport {
    private JsonSupport() {}
    public static int maxDepth() {
        try { int value=Integer.parseInt(System.getProperty("json.maxDepth", "100")); return value>0 ? Math.min(value,1000) : 100; }
        catch(NumberFormatException e) { return 100; }
    }
    public static JsonFactory factory() {
        return JsonFactory.builder()
            .streamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(maxDepth()).build())
            .streamWriteConstraints(StreamWriteConstraints.builder().maxNestingDepth(maxDepth()).build())
            .enable(JsonReadFeature.ALLOW_SINGLE_QUOTES,JsonReadFeature.ALLOW_UNQUOTED_FIELD_NAMES,
                    JsonReadFeature.ALLOW_JAVA_COMMENTS,
                    JsonReadFeature.ALLOW_TRAILING_COMMA,JsonReadFeature.ALLOW_MISSING_VALUES)
            .disable(StreamWriteFeature.AUTO_CLOSE_TARGET,StreamWriteFeature.AUTO_CLOSE_CONTENT)
            .build();
    }
    static Object parse(String text) {
        try(JsonParser parser=factory().createParser(LegacySyntax.translate(text))) {
            JsonToken token=parser.nextToken();
            if(token==null) throw new JSONException("Empty JSON input");
            Object value=read(parser,token);
            if(parser.nextToken()!=null) throw new JSONException("Trailing content after JSON value");
            return value;
        } catch(IOException e) {
            JsonLocation location=e instanceof JsonProcessingException ? ((JsonProcessingException)e).getLocation() : null;
            throw new JSONException("Malformed JSON"+(location==null ? "" : " at line "+location.getLineNr()+", column "+location.getColumnNr()));
        }
    }
    private static String safeLocation(JsonParser parser) { JsonLocation at=parser.currentLocation();return "line "+at.getLineNr()+", column "+at.getColumnNr(); }
    private static Object read(JsonParser parser,JsonToken token) throws IOException {
        switch(token) {
        case START_OBJECT:
            JSONObject object=new JSONObject();
            while(parser.nextToken()!=JsonToken.END_OBJECT) {
                if(parser.currentToken()!=JsonToken.FIELD_NAME) throw new JSONException("Expected object field at " + safeLocation(parser));
                String key=parser.currentName(); JsonToken valueToken=parser.nextToken();
                if(valueToken==null) throw new JSONException("Missing value at " + safeLocation(parser));
                Object nextValue=read(parser,valueToken);
                if(object.has(key)) {
                    Object prior=object.get(key);
                    JSONArray values=prior instanceof JSONArray ? (JSONArray)prior : new JSONArray();
                    if(!(prior instanceof JSONArray))values.rawAdd(prior);
                    values.rawAdd(nextValue);object.rawPut(key,values);
                } else object.rawPut(key,nextValue);
            }
            return object;
        case START_ARRAY:
            JSONArray array=new JSONArray();
            while(parser.nextToken()!=JsonToken.END_ARRAY) {
                if(parser.currentToken()==null) throw new JSONException("Unclosed array at " + safeLocation(parser));
                array.rawAdd(read(parser,parser.currentToken()));
            }
            return array;
        case VALUE_NULL:return JSONNull.getInstance();
        case VALUE_TRUE:return Boolean.TRUE;
        case VALUE_FALSE:return Boolean.FALSE;
        case VALUE_STRING:return parser.getText();
        case VALUE_NUMBER_INT:return parser.getNumberValue();
        case VALUE_NUMBER_FLOAT:return parser.getDoubleValue();
        default:throw new JSONException("Unexpected JSON token at " + safeLocation(parser));
        }
    }
    static Object normalize(Object value) { return normalize(value,new IdentityHashMap<Object,Boolean>(),0); }
    private static Object normalize(Object value,IdentityHashMap<Object,Boolean> active,int depth) {
        if(depth>maxDepth()) throw new JSONException("JSON nesting limit exceeded");
        if(value==null || value instanceof JSONNull) return JSONNull.getInstance();
        if(value instanceof String || value instanceof Boolean) return value;
        if(value instanceof Character || value instanceof Enum || value instanceof java.util.UUID) return String.valueOf(value);
        if(value instanceof Number) { checkNumber((Number)value); return value; }
        if(value instanceof JSONObject || value instanceof JSONArray) return value;
        if(value instanceof Class || value instanceof ClassLoader || value instanceof java.lang.reflect.Member) throw new JSONException("Class introspection is unavailable");
        if(active.put(value,Boolean.TRUE)!=null) throw new JSONException("Cyclic JSON value");
        try {
            if(value instanceof Map) {
                JSONObject result=new JSONObject();
                for(Object entryObject:((Map)value).entrySet()) { Map.Entry entry=(Map.Entry)entryObject; if(entry.getKey()==null)throw new JSONException("Object key is null"); result.rawPut(String.valueOf(entry.getKey()),normalize(entry.getValue(),active,depth+1)); }
                return result;
            }
            if(value instanceof Collection || value.getClass().isArray()) {
                JSONArray result=new JSONArray();
                if(value instanceof Collection) for(Object item:(Collection)value)result.rawAdd(normalize(item,active,depth+1));
                else for(int i=0;i<Array.getLength(value);i++)result.rawAdd(normalize(Array.get(value,i),active,depth+1));
                return result;
            }
            JSONObject result=new JSONObject();
            for(PropertyDescriptor property:Introspector.getBeanInfo(value.getClass(),Object.class).getPropertyDescriptors()) {
                String key=property.getName(); Method method=property.getReadMethod();
                if(method!=null && !key.equals("class") && !key.equals("classLoader") && !Class.class.isAssignableFrom(method.getReturnType()) && !ClassLoader.class.isAssignableFrom(method.getReturnType()))
                    result.rawPut(key,normalize(method.invoke(value),active,depth+1));
            }
            return result;
        } catch(JSONException e) { throw e; }
        catch(Exception e) { throw new JSONException("Cannot serialize JavaBean",e); }
        finally { active.remove(value); }
    }
    static void checkNumber(Number number) {
        if(!(number.getClass()==Byte.class || number.getClass()==Short.class || number.getClass()==Integer.class || number.getClass()==Long.class || number.getClass()==Float.class || number.getClass()==Double.class || number.getClass()==BigInteger.class || number.getClass()==BigDecimal.class))
            throw new JSONException("Unsupported numeric value type");
        if(number instanceof Double && !Double.isFinite(number.doubleValue()) || number instanceof Float && !Float.isFinite(number.floatValue())) throw new JSONException("JSON number is not finite");
    }
    static Number number(Object value) {
        if(value instanceof Number) return (Number)value;
        try { return new BigDecimal(String.valueOf(value)); } catch(NumberFormatException e) { throw new JSONException("Not a number",e); }
    }
    static boolean booleanValue(Object value) {
        if(Boolean.TRUE.equals(value) || "true".equalsIgnoreCase(String.valueOf(value))) return true;
        if(Boolean.FALSE.equals(value) || "false".equalsIgnoreCase(String.valueOf(value))) return false;
        throw new JSONException("Not a boolean");
    }
    public static String text(Object value,int indentation) { StringWriter writer=new StringWriter();write(value,writer,indentation);return writer.toString(); }
    public static Writer write(Object value,Writer writer,int indentation) {
        try (JsonGenerator generator=factory().createGenerator(writer)) {
            if(indentation>0) {
                DefaultPrettyPrinter printer=new DefaultPrettyPrinter();
                String spaces=" ".repeat(Math.min(indentation,100));
                printer.indentObjectsWith(new DefaultIndenter(spaces,"\n")); printer.indentArraysWith(new DefaultIndenter(spaces,"\n"));
                generator.setPrettyPrinter(printer);
            }
            emit(generator,normalize(value),new IdentityHashMap<Object,Boolean>(),0); generator.flush();
            return writer;
        } catch(IOException e) { throw new JSONException("Cannot write JSON"); }
    }
    public static void emit(JsonGenerator generator,Object input) throws IOException { emit(generator,normalize(input),new IdentityHashMap<Object,Boolean>(),0); }
    private static void emit(JsonGenerator generator,Object value,IdentityHashMap<Object,Boolean> active,int depth) throws IOException {
        if(depth>maxDepth()) throw new JSONException("JSON nesting limit exceeded");
        if(value==null || value==JSONNull.getInstance() || value instanceof JSONObject && ((JSONObject)value).isNullObject()) { generator.writeNull(); return; }
        if(value instanceof String) { generator.writeString((String)value); return; }
        if(value instanceof Boolean) { generator.writeBoolean((Boolean)value); return; }
        if(value instanceof Number) { checkNumber((Number)value); String raw=value.toString();
            if(raw.indexOf('.')>=0 && raw.indexOf('E')<0 && raw.indexOf('e')<0) {
                BigDecimal decimal=new BigDecimal(raw);
                raw=decimal.signum()==0 && raw.startsWith("-") ? "-0" : decimal.stripTrailingZeros().toPlainString();
            }
            generator.writeNumber(raw); return; }
        if(active.put(value,Boolean.TRUE)!=null) throw new JSONException("Cyclic JSON value");
        try {
            if(value instanceof JSONObject) {
                generator.writeStartObject();
                for(Map.Entry<Object,Object> entry:((JSONObject)value).entrySet()) { generator.writeFieldName(String.valueOf(entry.getKey())); emit(generator,entry.getValue(),active,depth+1); }
                generator.writeEndObject();
            } else if(value instanceof JSONArray) {
                generator.writeStartArray(); for(Object item:(JSONArray)value)emit(generator,item,active,depth+1);generator.writeEndArray();
            } else throw new JSONException("Unconverted JSON value");
        } finally { active.remove(value); }
    }
}
