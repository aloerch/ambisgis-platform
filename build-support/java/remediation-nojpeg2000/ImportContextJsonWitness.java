// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
// Independently authored actual native importer HTTP boundary regression witness.
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import net.sf.json.JSONException;
import org.geoserver.catalog.impl.CatalogImpl;
import org.geoserver.importer.*;
import org.geoserver.importer.job.JobQueue;
import org.geoserver.importer.rest.ImportLayer;
import org.geoserver.importer.rest.converters.*;
import org.geoserver.importer.transform.*;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpInputMessage;
import org.springframework.http.MediaType;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.HttpMessageNotReadableException;

public class ImportContextJsonWitness {
    static int checks;
    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
        checks++;
    }
    static class Input extends ByteArrayInputStream implements HttpInputMessage {
        boolean closed;
        Input(String body) { super(body.getBytes(StandardCharsets.UTF_8)); }
        public ByteArrayInputStream getBody() { return this; }
        public HttpHeaders getHeaders() {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            return headers;
        }
        public void close() throws IOException { closed = true; super.close(); }
    }
    @SuppressWarnings({"rawtypes", "unchecked"})
    static Object read(HttpMessageConverter converter, Class type, Input input) throws IOException {
        return converter.read(type, input);
    }
    @SuppressWarnings("rawtypes")
    public static void main(String[] args) throws Exception {
        boolean repaired = args[0].equals("repaired");
        // Real catalog, real importer and real in-memory storage. Reflection only
        // supplies its normally Spring-initialized store so native destroy works.
        Importer importer = new Importer(new CatalogImpl(), new ImporterInfoDAO());
        MemoryImportStore store = new MemoryImportStore(); store.init();
        Field contextStore = Importer.class.getDeclaredField("contextStore");
        contextStore.setAccessible(true); contextStore.set(importer, store);
        HttpMessageConverter[] converters = {
            new ImportContextJSONMessageConverter(importer),
            new ImportDataJSONMessageConverter(importer),
            new ImportLayerJSONMessageConverter(importer),
            new ImportTaskJSONMessageConverter(importer),
            new ImportTransformJSONMessageConverter(importer),
            new TransformChainJSONMessageConverter(importer)};
        Class[] types = {ImportContext.class, ImportData.class, ImportLayer.class,
            ImportTask.class, ImportTransform.class, TransformChain.class};
        String[] conversionErrors = {
            "{\"import\":{\"id\":\"private-request-marker\"}}", "{}",
            "{\"layer\":{\"bbox\":\"private-request-marker\"}}",
            "{\"task\":{\"id\":\"private-request-marker\"}}", "{}", "{}"};
        String[] valid = {
            "{\"import\":{\"id\":27,\"user\":\"ordinary-user\",\"archive\":true}}",
            "{\"type\":\"remote\",\"location\":\"https://example.invalid/fixture.tif\"}",
            "{\"layer\":{\"name\":\"sample\",\"title\":\"ordinary\"}}",
            "{\"task\":{\"id\":27,\"updateMode\":\"APPEND\"}}",
            "{\"type\":\"CreateIndexTransform\",\"field\":\"sample\"}",
            "{\"type\":\"vector\",\"transforms\":[{\"type\":\"CreateIndexTransform\",\"field\":\"sample\"}]}"};
        try {
            for (int index=0; index<converters.length; index++) {
                String name=converters[index].getClass().getSimpleName();
                for(String body:new String[]{"{\"private-request-marker\":",conversionErrors[index]}) {
                    Input input=new Input(body);
                    try {
                        read(converters[index],types[index],input);
                        throw new AssertionError(name+" accepted malformed JSON");
                    } catch(HttpMessageNotReadableException expected) {
                        check(repaired,name+" original unexpectedly mapped HTTP400");
                        check(expected.getMessage().equals("Malformed JSON import request."),name+" diagnostic not fixed");
                        check(expected.getCause()==null,name+" cause exposes request");
                    } catch(JSONException expected) {
                        check(!repaired,name+" unchecked JSON exception escaped repaired boundary");
                    }
                    check(input.closed,name+" rejected stream not closed");
                    Input good=new Input(valid[index]);
                    if(index==5&&!repaired) {
                        try { read(converters[index],types[index],good);throw new AssertionError("original chain failure disappeared"); }
                        catch(ValidationException expected) { check(expected.getMessage().equals("Invalid transform type 'vector'"),"unexpected original chain failure"); }
                        System.out.println("historical-chain-delegation-failure=preserved");
                    } else {
                        Object value=read(converters[index],types[index],good);
                        switch(index) {
                            case 0: ImportContext context=(ImportContext)value;check(context.getId()==27&&"ordinary-user".equals(context.getUser())&&context.isArchive(),"context recovery");break;
                            case 1: check(value instanceof RemoteData&&"https://example.invalid/fixture.tif".equals(((RemoteData)value).getLocation()),"remote data recovery without fetching");break;
                            case 2: ImportLayer layer=(ImportLayer)value;check("sample".equals(layer.getLayer().getName())&&"ordinary".equals(layer.getLayer().getResource().getTitle()),"layer recovery");break;
                            case 3: ImportTask task=(ImportTask)value;check(task.getId()==27&&task.getUpdateMode()==UpdateMode.APPEND&&task.getLayer()!=null,"task recovery");break;
                            case 4: check(value instanceof CreateIndexTransform&&"sample".equals(((CreateIndexTransform)value).getField()),"transform recovery");break;
                            case 5: TransformChain chain=(TransformChain)value;check(chain instanceof VectorTransformChain&&chain.getTransforms().size()==1&&"sample".equals(((CreateIndexTransform)chain.getTransforms().get(0)).getField()),"native vector chain recovery");break;
                            default: throw new AssertionError("unknown converter");
                        }
                    }
                    check(good.closed,name+" valid stream not closed");
                }
                System.out.println("native-converter="+name+" malformed=2 recovery="+(index==5&&!repaired?"historical-failure":"passed"));
            }
            Input raster=new Input("{\"type\":\"raster\",\"transforms\":[]}");
            if(repaired) {
                Object value=read(converters[5],TransformChain.class,raster);
                check(value instanceof RasterTransformChain&&((TransformChain)value).getTransforms().isEmpty(),"native empty raster chain recovery");
            } else {
                try {read(converters[5],TransformChain.class,raster);throw new AssertionError("original raster chain failure disappeared");}
                catch(ValidationException expected) {check(expected.getMessage().equals("Invalid transform type 'raster'"),"unexpected original raster failure");}
            }
            check(raster.closed,"raster chain stream not closed");
        } finally {
            // Native destroy closes the asynchronous queue/store; the separately
            // constructed synchronous fixture queue also has a scheduled cleaner.
            Field synchronous = Importer.class.getDeclaredField("synchronousJobs");
            synchronous.setAccessible(true);
            ((JobQueue)synchronous.get(importer)).shutdown();
            importer.destroy();
        }
        System.out.println("PASS checks="+checks+" converters=6 boundary="+args[0]);
    }
}
