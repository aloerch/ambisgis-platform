// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
import java.nio.file.Path;
/** Verifies live defining archives, separately from static inventory membership. */
public class LoadedOrigins {
 public static void main(String[] args)throws Exception{
  Path expected=Path.of(args[0]).toRealPath();
  for(String name:new String[]{"net.sf.json.JSON","net.sf.json.JSONObject","net.sf.json.JSONArray","net.sf.json.JSONNull","net.sf.json.JSONException","net.sf.json.JSONSerializer","net.sf.json.JsonSupport","net.sf.json.LegacySyntax","net.sf.json.util.JSONBuilder","net.sf.json.util.JSONStringer","net.sf.json.test.JSONAssert"}){
   Class<?> type=Class.forName(name,false,LoadedOrigins.class.getClassLoader());
   Path actual=Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
   if(!actual.equals(expected))throw new AssertionError("Foreign defining archive: "+name);
   System.out.println("verified-loaded-origin="+name);
  }
 }
}
