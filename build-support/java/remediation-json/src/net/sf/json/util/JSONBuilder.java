// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored selected-profile adapter; no json-lib implementation copied.
package net.sf.json.util;
import com.fasterxml.jackson.core.JsonGenerator;
import java.io.IOException;
import java.io.Writer;
import java.util.ArrayDeque;
import java.util.Deque;
import net.sf.json.JSONException;
import net.sf.json.JsonSupport;
/** Incremental compatibility writer backed by Jackson's checked output context. */
public class JSONBuilder {
    protected final Writer writer;
    private final JsonGenerator generator;
    private static final class Frame { final boolean object; boolean pending; Frame(boolean object){this.object=object;} }
    private final Deque<Frame> containers=new ArrayDeque<Frame>();
    private final int maximum=JsonSupport.maxDepth();
    private boolean started;
    private boolean failed;
    protected boolean complete;
    public JSONBuilder(Writer writer) {
        this.writer=writer;
        try { generator=JsonSupport.factory().createGenerator(writer); } catch(IOException e) { throw new JSONException(e); }
    }
    private JSONException reject(String message) {
        failed=true;
        try{generator.close();}catch(IOException ignored){}
        return new JSONException(message);
    }
    private interface Operation { void run() throws IOException; }
    private JSONBuilder perform(Operation operation) {
        if(complete || failed) throw reject("JSON document is complete or failed");
        try { operation.run();generator.flush();return this; }
        catch(IOException | RuntimeException e) { failed=true;try{generator.close();}catch(IOException ignored){}throw new JSONException("Invalid JSON writer state"); }
    }
    private JSONBuilder begin(final boolean object) {
        if(containers.size()>=maximum) throw reject("JSON nesting limit exceeded: " + maximum);
        perform(new Operation(){public void run()throws IOException{if(object)generator.writeStartObject();else generator.writeStartArray();}});
        if(!containers.isEmpty())containers.peek().pending=false;
        started=true;containers.push(new Frame(object));return this;
    }
    private JSONBuilder end(final boolean object) {
        if(containers.isEmpty() || containers.peek().object!=object) throw reject("Mismatched JSON container close");
        if(object && containers.peek().pending)throw reject("Object field has no value");
        perform(new Operation(){public void run()throws IOException{if(object)generator.writeEndObject();else generator.writeEndArray();}});
        containers.pop();complete=containers.isEmpty();
        if(complete)try{generator.close();}catch(IOException e){failed=true;throw new JSONException("Cannot finish JSON writer");}
        return this;
    }
    public JSONBuilder object(){return begin(true);}
    public JSONBuilder array(){return begin(false);}
    public JSONBuilder endObject(){return end(true);}
    public JSONBuilder endArray(){return end(false);}
    public JSONBuilder key(final String key) {
        if(key==null || containers.isEmpty() || !containers.peek().object || containers.peek().pending)throw reject("Object key outside object");
        perform(new Operation(){public void run()throws IOException{generator.writeFieldName(key);}});
        containers.peek().pending=true;return this;
    }
    public JSONBuilder value(final Object value) {
        if(!started || containers.isEmpty())throw reject("Value outside JSON container");
        perform(new Operation(){public void run()throws IOException{JsonSupport.emit(generator,value);}});
        containers.peek().pending=false;return this;
    }
    public JSONBuilder value(boolean value){return value(Boolean.valueOf(value));}
    public JSONBuilder value(double value){return value(Double.valueOf(value));}
    public JSONBuilder value(long value){return value(Long.valueOf(value));}
}
