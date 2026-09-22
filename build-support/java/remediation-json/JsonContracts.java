// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
import java.io.StringWriter;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.*;
import java.util.concurrent.*;
import net.sf.json.*;
import net.sf.json.util.*;
import org.geoserver.wfs.json.GeoJSONBuilder;
import org.locationtech.jts.geom.*;

/** Independent protocol, malformed-input and safety assertions; no donor implementation. */
public class JsonContracts {
    private static int assertions;
    private static void check(boolean value,String label){assertions++;if(!value)throw new AssertionError(label);}
    private static void refuses(Runnable operation,String label){try{operation.run();throw new AssertionError(label);}catch(JSONException expected){assertions++;check(expected.getMessage()!=null&&!expected.getMessage().isEmpty(),label+" diagnostic");}}
    public static class Bean { public String getName(){return "reader";} public boolean isEnabled(){return true;} public int getCount(){return 3;} }
    public static class SecretBean { public Class<?> getClassLoaderType(){return getClass();} public String getName(){return "safe";} }
    static void common(){
        JSONObject o=JSONObject.fromObject("{\"present\":null,\"zero\":0,\"false\":false,\"text\":\"水😀</script>\\u0000\\n\\t\\\\\\\"\",\"array\":[1,null,{}]}");
        check(o.has("present")&&!o.has("missing"),"null versus missing");check(o.get("missing")==null,"missing map value");
        check(o.get("present")==JSONNull.getInstance(),"explicit null singleton");check(o.getString("present").equals("null"),"null string");
        check(o.optString("missing","fallback").equals("fallback"),"missing fallback");check(o.optString("present","fallback").equals("null"),"null fallback");
        refuses(()->o.getString("missing"),"missing required value");refuses(()->o.getJSONArray("text"),"wrong array type");
        check(JSONObject.fromObject(o.toString()).getString("text").equals(o.getString("text")),"Unicode and control roundtrip");
        check(o.getJSONArray("array").getJSONObject(2).isEmpty(),"nested empty object");
        JSONObject n=JSONObject.fromObject("{\"i\":2147483647,\"l\":2147483648,\"large\":9223372036854775808,\"d\":1.25,\"exp\":1e3,\"minus\":-1}");
        check(n.get("i") instanceof Integer,"int type");check(n.get("l") instanceof Long,"long type");check(n.get("large") instanceof BigInteger,"big integer type");
        check(n.get("d") instanceof Double&&n.getDouble("d")==1.25,"fraction type");check(n.getDouble("exp")==1000,"exponent");
        for(String token:new String[]{"1e400","-1e400","1e-400"}) {
            JSONObject extreme=JSONObject.fromObject("{a:"+token+"}");
            check(extreme.get("a") instanceof BigDecimal && ((BigDecimal)extreme.get("a")).compareTo(new BigDecimal(token))==0,"finite exponent preserved "+token);
            check(((BigDecimal)JSONObject.fromObject(extreme.toString()).get("a")).compareTo(new BigDecimal(token))==0,"finite exponent roundtrip "+token);
        }
        BigDecimal precise=new BigDecimal("12345678901234567890.1234567890123456789");
        JSONObject preciseObject=new JSONObject().element("precise",precise);check(preciseObject.get("precise").equals(precise),"in-memory precision");check(preciseObject.toString().contains(precise.toString()),"serialized precision");
        for(String legacy:new String[]{"{'name':'reader'}","{name:'reader'}","{/*comment*/name:'reader'}","{name:'reader',}"})check(JSONObject.fromObject(legacy).getString("name").equals("reader"),"legacy "+legacy);
        check(JSONObject.fromObject("{a=1;a:2}").getJSONArray("a").getInt(1)==2,"legacy separators and duplicate accumulation");
        check(JSONArray.fromObject("[0x10,010]").getInt(0)==16&&JSONArray.fromObject("[0x10,010]").getInt(1)==8,"legacy integer radix");
        check(JSONArray.fromObject("[1,,3]").get(1)==JSONNull.getInstance(),"legacy missing array item");
        for(String malformed:new String[]{"{","[1","{\"a\":}","{\"a\":\"unterminated}","{\"a\":NaN}"})refuses(()->JSONSerializer.toJSON(malformed),"malformed "+malformed);
        refuses(()->new JSONObject().element("bad",Double.POSITIVE_INFINITY),"infinity");refuses(()->new JSONArray().add(Double.NaN),"NaN");
        JSONObject bean=JSONObject.fromObject(new Bean());check(bean.getString("name").equals("reader")&&bean.getBoolean("enabled")&&bean.getInt("count")==3,"bean properties");check(!bean.has("class"),"class property stays suppressed");
        Map<String,Object> source=new LinkedHashMap<String,Object>();source.put("roles",Arrays.asList("ROLE_READER","ROLE_PUBLISHER"));source.put("active",Boolean.TRUE);source.put("username","reader");
        JSONObject token=JSONObject.fromObject(source);check(token.getJSONArray("roles").size()==2&&token.getBoolean("active"),"token and role container conversion");
        JSONArray values=JSONArray.fromObject(new int[]{2,3});check(values.getInt(1)==3,"primitive array");
        check(JSONObject.fromObject((Object)null).isNullObject(),"null object");check(JSONSerializer.toJSON("null")==JSONNull.getInstance(),"null document");
        StringWriter writer=new StringWriter();JSONBuilder b=new JSONBuilder(writer);b.object().key("values").array().value(true).value(1.25).value(2L).value((Object)null).endArray().endObject();check(JSONObject.fromObject(writer.toString()).getJSONArray("values").size()==4,"writer stream");
        refuses(()->new JSONBuilder(new StringWriter()).object().key("missing").endObject(),"missing writer field value");
        refuses(()->b.array(),"second root");refuses(()->new JSONBuilder(new StringWriter()).key("outside"),"key outside object");refuses(()->new JSONBuilder(new StringWriter()).array().endObject(),"mismatched container");
        check(new JSONStringer().toString()==null,"incomplete stringer");check(new JSONStringer().array().value("reader").endArray().toString().equals("[\"reader\"]"),"completed stringer");
        StringWriter geometry=new StringWriter();new GeoJSONBuilder(geometry).writeGeom(new GeometryFactory().createPoint(new Coordinate(2.5,3.25)));JSONObject point=JSONObject.fromObject(geometry.toString());check(point.getString("type").equals("Point")&&point.getJSONArray("coordinates").getDouble(1)==3.25,"actual GeoServer WFS geometry writer");
        System.out.println("common-json-contracts="+assertions);
    }
    static void safety()throws Exception{
        int before=assertions;
        String marker="synthetic-secret-marker-0193";
        try{JSONObject.fromObject("{\"token\":"+marker+"}");throw new AssertionError("malformed secret accepted");}
        catch(JSONException e){StringWriter trace=new StringWriter();e.printStackTrace(new java.io.PrintWriter(trace));check(!trace.toString().contains(marker),"parser diagnostic does not disclose input");}
        Number custom=new Number(){public int intValue(){return 1;}public long longValue(){return 1;}public float floatValue(){return 1;}public double doubleValue(){return 1;}public String toString(){return "0,\"injected\":true";}};
        refuses(()->new JSONObject().element("number",custom),"custom number injection");
        refuses(()->JSONObject.fromObject("#comment\n{a:1}"),"YAML comments remain rejected");
        for(String token:new String[]{"1e2147483647","1e-2147483647"}) {
            String encoded=JSONObject.fromObject("{a:"+token+"}").toString();
            check(encoded.length()<40 && encoded.contains("E"),"extreme scale remains compact "+token);
        }
        try { JSONObject.fromObject("{a:1e2147483648}");throw new AssertionError("out-of-range exponent accepted"); }
        catch(JSONException e) { check(e.getCause()==null && !e.getMessage().contains("2147483648"),"out-of-range exponent sanitized"); }
        refuses(()->JSONArray.fromObject("[1 2]"),"ambiguous unquoted array text is rejected");
        refuses(()->JSONObject.fromObject(Bean.class),"class object unavailable");check(!JSONObject.fromObject(new SecretBean()).has("classLoaderType"),"class-returning property suppressed");
        JSONObject metadata=JSONObject.fromObject("{\"@class\":\"java.lang.ProcessBuilder\",\"command\":[\"unused\"]}");check(metadata.getString("@class").equals("java.lang.ProcessBuilder"),"type metadata stays data");
        refuses(()->JSONObject.fromObject("{\"a\":1} trailing"),"trailing garbage");
        refuses(()->JSONArray.fromObject("[0x"+"f".repeat(1001)+"]"),"legacy number bound");
        String deep="[".repeat(101)+"0"+"]".repeat(101);refuses(()->JSONArray.fromObject(deep),"parser depth bound");
        StringWriter invalidWriter=new StringWriter();JSONBuilder invalidBuilder=new JSONBuilder(invalidWriter).object().key("a");
        refuses(()->invalidBuilder.endObject(),"missing value cannot close");
        refuses(()->invalidBuilder.value("later"),"failed writer cannot resume");
        check(!invalidWriter.toString().endsWith("}"),"failure cannot manufacture a completed object");
        Map<String,Object> cycle=new HashMap<String,Object>();cycle.put("cycle",cycle);refuses(()->JSONObject.fromObject(cycle),"map cycle");
        JSONObject self=new JSONObject();self.element("self",self);refuses(()->self.toString(),"mutable wrapper cycle");
        String function="function(){ throw 'must remain data'; }";check(JSONObject.fromObject(new JSONObject().element("text",function).toString()).getString("text").equals(function),"function-like strings remain strings");
        ExecutorService executor=Executors.newFixedThreadPool(4);List<Future<Boolean>> results=new ArrayList<Future<Boolean>>();
        try{for(int i=0;i<80;i++){final int index=i;results.add(executor.submit(()->JSONObject.fromObject(new JSONObject().element("n",index).toString()).getInt("n")==index));}for(Future<Boolean> result:results)check(result.get(),"concurrent independent parse");}finally{executor.shutdownNow();}
        System.out.println("safe-json-contracts="+(assertions-before));
    }
    public static void main(String[] args)throws Exception{common();if(args.length>0&&args[0].equals("safety"))safety();}
}
