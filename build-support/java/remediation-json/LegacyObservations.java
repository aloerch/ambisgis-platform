// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
import net.sf.json.*;
import net.sf.json.util.*;
import java.io.StringWriter;
/** Records narrow baseline grammar observations; never evaluates function text. */
public class LegacyObservations {
 public static void main(String[] args){
  for(String text:new String[]{"[1 2]","{a:word}","{a=1}","{a:1;a:2}","{a:1,a:2}","#comment\n{a:1}","[1,]","{a:undefined}","{a:NaN}","{a:Infinity}","[0x10,010]","{a:1} trailing"}){
   try{JSON value=JSONSerializer.toJSON(text);System.out.println(text.replace("\n","\\n")+" -> "+value.toString());}catch(JSONException e){System.out.println(text.replace("\n","\\n")+" -> refused");}
  }
  StringWriter w=new StringWriter();try{new JSONBuilder(w).object().key("a").value(1).key("a").value(2).endObject();System.out.println("duplicate-builder -> "+w);}catch(JSONException e){System.out.println("duplicate-builder -> refused");}
  w=new StringWriter();try{new JSONBuilder(w).object().key("a").endObject();System.out.println("missing-builder-value -> "+w);}catch(JSONException e){System.out.println("missing-builder-value -> refused");}
 }
}
