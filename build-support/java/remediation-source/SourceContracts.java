import java.io.StringReader;
import java.io.StringWriter;
import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;
import net.sf.json.*;
import net.sf.json.util.JSONBuilder;
import org.xmlpull.v1.*;
import com.thoughtworks.xstream.XStream;
import com.thoughtworks.xstream.io.xml.MXParserDriver;
import org.springframework.aop.aspectj.annotation.AspectJProxyFactory;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.*;

public class SourceContracts {
  static int assertions;
  static void check(boolean pass, String reason) { assertions++; if (!pass) throw new AssertionError(reason); }
  public static class Service { public String invoke(String x) { return "ok:"+x; } }
  @Aspect public static class Advice {
    static int calls;
    @Around("execution(* SourceContracts.Service.invoke(..))")
    public Object around(ProceedingJoinPoint p) throws Throwable {calls++; return p.proceed();}
  }
  static void json() {
    JSONObject o=JSONObject.fromObject("{\"n\":null,\"zero\":0,\"dec\":1.25,\"yes\":true,\"escape\":\"a\\n\\t\\\"\\\\b\",\"unicode\":\"Grüße 水\",\"array\":[1,null,false]}");
    check(o.get("n")==JSONNull.getInstance(),"JSON null");
    check(o.getInt("zero")==0 && o.getDouble("dec")==1.25,"JSON numbers");
    check(o.getString("escape").equals("a\n\t\"\\b"),"JSON escaping");
    check(JSONObject.fromObject(o.toString()).equals(o),"JSON round trip");
    JSONArray roles=JSONObject.fromObject("{\"roles\":[\"ROLE_READER\",\"ROLE_PUBLISHER\"]}").getJSONArray("roles");
    check(roles.size()==2 && roles.getString(0).equals("ROLE_READER"),"role response shape");
    check(JSONObject.fromObject("{\"active\":true,\"username\":\"reader\",\"scope\":\"read\"}").getBoolean("active"),"OAuth shape");
    StringWriter writer=new StringWriter();
    new JSONBuilder(writer).object().key("type").value("FeatureCollection").key("features").array().object().key("type").value("Feature").key("geometry").object().key("type").value("Point").key("coordinates").array().value(2.5).value(3.25).endArray().endObject().key("properties").object().key("text").value("水\nquote\"").key("n").value(null).endObject().endObject().endArray().endObject();
    check(JSONObject.fromObject(writer.toString()).getJSONArray("features").getJSONObject(0).getJSONObject("geometry").getJSONArray("coordinates").getDouble(1)==3.25,"WFS encoding shape");
    check(JSONObject.fromObject("{\"layer\":{\"name\":\"witness\",\"enabled\":true}}").getJSONObject("layer").getBoolean("enabled"),"REST shape");
    for(int i=0;i<200;i++) {
      String text="entry-"+i+"\n\t\r\b\f\\\"水";
      JSONObject p=new JSONObject();p.element("s",text);p.element("n",new BigDecimal("12345.25"));
      JSONObject back=JSONObject.fromObject(p.toString());
      check(back.getString("s").equals(text)&&back.getDouble("n")==12345.25,"repeat serialization");
    }
    for(String setting:new String[]{null,"8","0","bad"}) {
      if(setting==null)System.clearProperty("json.maxDepth"); else System.setProperty("json.maxDepth",setting);
      JSONBuilder b=new JSONBuilder(new StringWriter());int depth=0;
      try { for(;depth<10000;depth++)b.array(); throw new AssertionError("unbounded builder"); }
      catch(JSONException expected) {System.out.println("builder-depth:"+setting+"="+depth);check(depth>0&&depth<10000,"bounded depth");}
    }
    System.clearProperty("json.maxDepth");
    try {new JSONObject().element("bad",Double.NaN);throw new AssertionError("NaN accepted");}catch(JSONException expected){assertions++;}
    System.out.println("json-contracts="+assertions);
  }
  static void xml() throws Exception {
    XmlPullParserFactory f=XmlPullParserFactory.newInstance();
    f.setNamespaceAware(true);XmlPullParser p=f.newPullParser();
    check(p.getClass().getName().equals("io.github.xstream.mxparser.MXParser"),"actual provider");
    p.setInput(new StringReader("<r xmlns=\"urn:fixture\"><n value=\"3\">safe &amp; valid</n></r>"));
    int starts=0;String text="";
    while(p.next()!=XmlPullParser.END_DOCUMENT){if(p.getEventType()==XmlPullParser.START_TAG){starts++;check(p.getNamespace().equals("urn:fixture"),"namespace");}if(p.getEventType()==XmlPullParser.TEXT)text+=p.getText();}
    check(starts==2&&text.equals("safe & valid"),"XML parse");
    XmlPullParser explicit=XmlPullParserFactory.newInstance("io.github.xstream.mxparser.MXParser",SourceContracts.class).newPullParser();
    check(explicit.getClass()==p.getClass(),"explicit factory");
    try {f.newSerializer();throw new AssertionError("absent serializer accepted");}catch(XmlPullParserException expected){assertions++;}
    try {XmlPullParserFactory.newInstance("absent.NoProvider",SourceContracts.class).newPullParser();throw new AssertionError("absent provider accepted");}catch(XmlPullParserException expected){assertions++;}
    p.setInput(new StringReader("<r></z>"));try{while(p.next()!=XmlPullParser.END_DOCUMENT){}throw new AssertionError("bad XML accepted");}catch(XmlPullParserException expected){check(expected.getLineNumber()>0,"exception location");}
    XStream x=new XStream(new MXParserDriver());x.allowTypes(new Class[]{LinkedHashMap.class,String.class,Integer.class});
    Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("name","XML & service");value.put("count",Integer.valueOf(3));
    String encoded=x.toXML(value);check(x.fromXML(encoded).equals(value),"actual XStream round trip");
    try{x.fromXML("<java.lang.ProcessBuilder><command><string>unused</string></command></java.lang.ProcessBuilder>");throw new AssertionError("XStream permissions weakened");}catch(com.thoughtworks.xstream.security.ForbiddenClassException expected){assertions++;}
    System.out.println("xml-provider="+p.getClass().getName());System.out.println("xml-contracts="+assertions);
  }
  static void proxy() {
    AspectJProxyFactory factory=new AspectJProxyFactory(new Service());factory.addAspect(Advice.class);Service proxy=factory.getProxy();
    check(proxy.invoke("fixture").equals("ok:fixture"),"proxy returned value");check(Advice.calls==1,"actual AspectJ advice executed");
    System.out.println("aspectj-proxy-contracts="+assertions);
  }
  public static void main(String[] args)throws Exception {if(args[0].equals("json"))json();else if(args[0].equals("xml"))xml();else proxy();}
}
