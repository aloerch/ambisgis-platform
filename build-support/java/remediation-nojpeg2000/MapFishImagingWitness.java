import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.imageio.ImageIO;
import org.mapfish.print.MapPrinter;
import org.mapfish.print.ShellMapPrinter;
import org.springframework.context.support.ClassPathXmlApplicationContext;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.apache.pdfbox.text.PDFTextStripper;
public class MapFishImagingWitness {
 static void checkRaster(BufferedImage image,String name)throws Exception {
  if(image==null||image.getWidth()<300||image.getHeight()<300)throw new AssertionError(name+" dimensions");
  int colored=0;for(int y=0;y<image.getHeight();y++)for(int x=0;x<image.getWidth();x++){int rgb=image.getRGB(x,y),r=(rgb>>>16)&255,g=(rgb>>>8)&255,b=rgb&255;if(Math.max(r,Math.max(g,b))-Math.min(r,Math.min(g,b))>30)colored++;}
  if(colored<2000)throw new AssertionError(name+" missing known raster content: "+colored);System.out.println("mapfish_decoded format="+name+" width="+image.getWidth()+" height="+image.getHeight()+" colored_pixels="+colored);
 }
 public static void main(String[]args)throws Exception {
  if(System.getProperty("ambisgis.witness.renderer")!=null)RenderingWitness.main(new String[]{System.getProperty("ambisgis.witness.renderer"),System.getProperty("ambisgis.witness.renderer.sha256")});

  Path out=Path.of(args[0]);Files.createDirectories(out);Path fixture=out.resolve("known.png");ImageIO.write(NoJpegImageIOWitness.sample(true),"PNG",fixture.toFile());
  String yaml="dpis: [72]\nformats: ['*']\nscales: [1000]\nhosts:\n  - !localMatch\n    dummy: true\nlayouts:\n  witness:\n    mainPage:\n      pageSize: A4\n      items:\n        - !text\n          text: 'AmbisGIS printing codec witness'\n          fontSize: 18\n        - !image\n          maxWidth: 192\n          maxHeight: 160\n          url: '"+fixture.toUri()+"'\n";
  Path config=out.resolve("print.yaml");Files.writeString(config,yaml);
  try(ClassPathXmlApplicationContext context=new ClassPathXmlApplicationContext(ShellMapPrinter.DEFAULT_SPRING_CONTEXT)){
   MapPrinter printer=context.getBean(MapPrinter.class);printer.setYamlConfigFile(config.toFile());
   try {for(String format:new String[]{"pdf","png","tiff"}){
    Path target=out.resolve("print."+format);String spec="{\"layout\":\"witness\",\"outputFormat\":\""+format+"\",\"dpi\":72,\"units\":\"m\",\"srs\":\"EPSG:4326\",\"layers\":[],\"pages\":[{\"center\":[0,0],\"scale\":1000,\"rotation\":0}]}";
    try(OutputStream stream=Files.newOutputStream(target)){printer.print(MapPrinter.parseSpec(spec),stream,Collections.emptyMap());}
    if(format.equals("pdf")){try(PDDocument pdf=Loader.loadPDF(target.toFile())){if(pdf.getNumberOfPages()!=1||!new PDFTextStripper().getText(pdf).contains("AmbisGIS printing codec witness"))throw new AssertionError("PDF text/page contract");BufferedImage image=new PDFRenderer(pdf).renderImageWithDPI(0,72);checkRaster(image,format);ImageIO.write(image,"PNG",out.resolve("pdf-decoded.png").toFile());}}
    else checkRaster(ImageIO.read(target.toFile()),format);
   }}finally{printer.stop();}
  }
  System.out.println("MAPFISH_IMAGING_WITNESS_PASS");
 }
}
