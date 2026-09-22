/* Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0 */
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import javax.imageio.*;
import javax.imageio.stream.*;
import org.mapfish.print.*;
import org.mapfish.print.output.InMemoryJaiMosaicOutputFactory;
import org.springframework.context.support.ClassPathXmlApplicationContext;

public class Jpeg2000RemovalWitness {
    interface Action { void run() throws Exception; }
    static int rejected;
    public static class PrintServlet extends org.mapfish.print.servlet.MapPrinterServlet {
        public void respond(javax.servlet.http.HttpServletResponse response, Throwable failure) { error(response, failure); }
    }
    static void response(int expected, Throwable failure, String expectedText) throws Exception {
        int[] status={0}; StringWriter text=new StringWriter();
        javax.servlet.http.HttpServletResponse target=(javax.servlet.http.HttpServletResponse)java.lang.reflect.Proxy.newProxyInstance(
            Jpeg2000RemovalWitness.class.getClassLoader(),new Class<?>[]{javax.servlet.http.HttpServletResponse.class},
            (proxy,method,args)-> {
                if(method.getName().equals("setStatus")){status[0]=(int)args[0];return null;}
                if(method.getName().equals("getWriter"))return new PrintWriter(text);
                if(method.getReturnType()==boolean.class)return false;
                if(method.getReturnType()==int.class)return 0;
                if(method.getReturnType()==long.class)return 0L;
                return null;
            });
        new PrintServlet().respond(target,failure);
        if(status[0]!=expected || !text.toString().contains(expectedText) || text.toString().contains("private-detail") || text.toString().contains("Exception"))throw new AssertionError("mapped print error "+status[0]+" "+text);
        System.out.println("print_error_status="+status[0]+" bounded_redacted_body=true");
    }

    static void unsupported(String label, Action action) throws Exception {
        try { action.run(); throw new AssertionError("accepted " + label); }
        catch (Throwable failure) {
            if (!Jpeg2000Policy.isUnsupported(failure)) throw new AssertionError("wrong refusal " + label, failure);
            rejected++;
            System.out.println("unsupported=" + label + " message=" + Jpeg2000Policy.MESSAGE);
        }
    }
    static String spec(String format) {
        return "{\"layout\":\"witness\",\"outputFormat\":\""+format+"\",\"dpi\":72,\"units\":\"m\",\"srs\":\"EPSG:4326\",\"layers\":[],\"pages\":[{\"center\":[0,0],\"scale\":1000,\"rotation\":0}]}";
    }
    public static void main(String[] args) throws Exception {
        Path out=Path.of(args[0]); Files.createDirectories(out);
        for(String type: new String[]{"jj2000.j2k.JJ2KInfo", "com.sun.media.imageioimpl.plugins.jpeg2000.J2KImageReaderSpi", "com.sun.media.imageioimpl.plugins.jpeg2000.J2KImageWriterSpi"}) {
            try {Class.forName(type); throw new AssertionError("blocked runtime class " + type);}
            catch(ClassNotFoundException expected) {System.out.println("absent_class="+type);}
        }
        for(String format: new String[]{"JPEG2000","jpeg2000","JP2","jp2","J2K","j2k"}) {
            if(ImageIO.getImageReadersByFormatName(format).hasNext() || ImageIO.getImageWritersByFormatName(format).hasNext()) throw new AssertionError("provider " + format);
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            if(ImageIO.write(NoJpegImageIOWitness.sample(false),format,bytes) || bytes.size()!=0) throw new AssertionError("silent output conversion " + format);
        }
        for(String format: new InMemoryJaiMosaicOutputFactory().formats()) {
            try { Jpeg2000Policy.checkOutput(format); }
            catch(Jpeg2000Policy.UnsupportedFormat failure) {throw new AssertionError("advertised blocked format " + format);}
        }
        byte[] png=Files.readAllBytes(Path.of(args[1]));
        for(String kind:new String[]{"jp2","ordinary"}) {
            Path pdfFile=out.resolve(kind+"-embedded.pdf");
            try(OutputStream stream=Files.newOutputStream(pdfFile)) {
                com.lowagie.text.Document doc=new com.lowagie.text.Document();
                com.lowagie.text.pdf.PdfWriter.getInstance(doc,stream);doc.open();
                // Independent fixture generation deliberately bypasses the policy.
                doc.add(com.lowagie.text.Image.getInstance(kind.equals("jp2")?Files.readAllBytes(out.resolve("input.jp2")):png));
                doc.close();
            }
            if(kind.equals("jp2"))unsupported("PDF-JPXDecode",()->Jpeg2000Policy.loadPdf(pdfFile.toString()));
            else {com.lowagie.text.pdf.PdfReader reader=Jpeg2000Policy.loadPdf(pdfFile.toString());reader.close();}
        }

        // Positive successor operations are interleaved with refused requests.
        try(ClassPathXmlApplicationContext context=new ClassPathXmlApplicationContext(ShellMapPrinter.DEFAULT_SPRING_CONTEXT)) {
            MapPrinter printer=context.getBean(MapPrinter.class);
            try {
                Path yaml=out.resolve("print.yaml");
                for(String fixture: new String[]{"input.jp2","raw.j2k","disguised.png","raw-disguised.tif"}) {
                    Path file=out.resolve(fixture); byte[] data=Files.readAllBytes(file);
                    try(ImageInputStream stream=ImageIO.createImageInputStream(file.toFile())) {
                        if(ImageIO.getImageReaders(stream).hasNext()) throw new AssertionError("content reader " + fixture);
                    }
                    unsupported("bytes-"+fixture,()->Jpeg2000Policy.load(data));
                    unsupported("url-"+fixture,()->Jpeg2000Policy.load(file.toUri().toURL()));
                    for(String uri: new String[]{file.toUri().toString(),"data:image/png;base64,"+Base64.getEncoder().encodeToString(data)}) {
                        String config="dpis: [72]\nformats: ['*']\nscales: [1000]\nhosts:\n  - !localMatch\n    dummy: true\nlayouts:\n  witness:\n    mainPage:\n      pageSize: A4\n      items:\n        - !image\n          maxWidth: 192\n          maxHeight: 160\n          url: '"+uri+"'\n";
                        Files.writeString(yaml,config);printer.setYamlConfigFile(yaml.toFile());
                        unsupported("mapfish-"+fixture+"-"+(uri.startsWith("data:")?"data":"file"),()->printer.print(MapPrinter.parseSpec(spec("pdf")),new ByteArrayOutputStream(),Collections.emptyMap()));
                    }
                    if(Jpeg2000Policy.load(png).getWidth()!=96)throw new AssertionError("recovery after "+fixture);
                }
                for(String kind:new String[]{"jp2","ordinary"}) {
                    String config="dpis: [72]\nformats: ['*']\nscales: [1000]\nhosts:\n  - !localMatch\n    dummy: true\nlayouts:\n  witness:\n    mainPage:\n      pageSize: A4\n      backgroundPdf: '"+out.resolve(kind+"-embedded.pdf")+"'\n      items:\n        - !text\n          text: 'Background PDF witness'\n";
                    Files.writeString(yaml,config);printer.setYamlConfigFile(yaml.toFile());
                    if(kind.equals("jp2"))unsupported("mapfish-background-JPXDecode",()->printer.print(MapPrinter.parseSpec(spec("pdf")),new ByteArrayOutputStream(),Collections.emptyMap()));
                    else printer.print(MapPrinter.parseSpec(spec("pdf")),new ByteArrayOutputStream(),Collections.emptyMap());
                }
                for(String position:new String[]{"header","footer"}) {
                    String config="dpis: [72]\nformats: ['*']\nscales: [1000]\nhosts:\n  - !localMatch\n    dummy: true\nlayouts:\n  witness:\n    mainPage:\n      pageSize: A4\n      "+position+":\n        height: 50\n        items:\n          - !image\n            maxWidth: 96\n            maxHeight: 40\n            url: '"+out.resolve("input.jp2").toUri()+"'\n      items:\n        - !text\n          text: 'Final-page body witness'\n";
                    Files.writeString(yaml,config);printer.setYamlConfigFile(yaml.toFile());
                    unsupported("mapfish-final-page-"+position,()->printer.print(MapPrinter.parseSpec(spec("pdf")),new ByteArrayOutputStream(),Collections.emptyMap()));
                }
                for(String format: new String[]{"JPEG2000","jp2","J2K","image/jp2","image/jpeg2000; q=1","JPEG 2000","jpf","image/x-jp2","jpm","mj2","x-jpeg2000"}) {
                    unsupported("mapfish-output-"+format,()->printer.getOutputFormat(MapPrinter.parseSpec(spec(format))));
                    unsupported("direct-print-output-"+format,()->printer.print(MapPrinter.parseSpec(spec(format)),new ByteArrayOutputStream(),Collections.emptyMap()));
                }
                unsupported("truncated-raw",()->Jpeg2000Policy.load(new byte[]{(byte)255,79}));
                unsupported("truncated-container",()->Jpeg2000Policy.load(new byte[]{0,0,0,12,106,80,32,32}));
            } finally {printer.stop();}
        }
        response(415,new RuntimeException("private-detail",new Jpeg2000Policy.UnsupportedFormat()),Jpeg2000Policy.MESSAGE);
        response(415,new com.lowagie.text.ExceptionConverter(new Jpeg2000Policy.UnsupportedFormat()),Jpeg2000Policy.MESSAGE);
        response(413,new RuntimeException("private-detail",new Jpeg2000Policy.InputLimit()),Jpeg2000Policy.LIMIT_MESSAGE);
        try {Jpeg2000Policy.load(new byte[Jpeg2000Policy.MAX_IMAGE_BYTES+1]);throw new AssertionError("oversize image accepted");}
        catch(Jpeg2000Policy.InputLimit expected) {System.out.println("oversize_bytes_refused=true");}
        URL declaredOversize=new URL(null,"memory:oversize",new URLStreamHandler(){
            protected URLConnection openConnection(URL u){return new URLConnection(u){
                public void connect() { }
                public long getContentLengthLong(){return (long)Jpeg2000Policy.MAX_IMAGE_BYTES+1;}
                public InputStream getInputStream(){throw new AssertionError("oversize content opened");}
            };}
        });
        try {Jpeg2000Policy.load(declaredOversize);throw new AssertionError("oversize URL accepted");}
        catch(Jpeg2000Policy.InputLimit expected){System.out.println("oversize_url_refused_before_read=true");}
        for(byte[] malformed: new byte[][]{new byte[0],new byte[]{0},new byte[]{(byte)255}}) {
            try {Jpeg2000Policy.load(malformed);throw new AssertionError("malformed accepted");}
            catch(IOException|com.lowagie.text.BadElementException expected){System.out.println("malformed_input_refused=true");}
        }
        if(Jpeg2000Policy.load(png).getWidth()!=96)throw new AssertionError("valid recovery");
        System.out.println("NOJPEG2000_NEGATIVE_PASS rejections="+rejected);
    }
}
