// Candidate-specific successor; original JPEG2000-positive witness is preserved.
import javax.imageio.*;
import javax.imageio.spi.*;
import javax.imageio.stream.*;
import javax.imageio.metadata.*;
import java.awt.*;
import java.awt.image.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import com.sun.media.imageio.plugins.tiff.*;
public class NoJpegImageIOWitness {
 static String origin(Class<?> c) {return String.valueOf(c.getProtectionDomain().getCodeSource());}
 static void inventory() {
  ImageIO.scanForPlugins();IIORegistry r=IIORegistry.getDefaultInstance();
  for(Class<?> type: new Class<?>[]{ImageReaderSpi.class,ImageWriterSpi.class,ImageInputStreamSpi.class,ImageOutputStreamSpi.class}) {
   Iterator<?> i=r.getServiceProviders(type,true);int order=0;while(i.hasNext()){Object p=i.next();System.out.println("provider category="+type.getSimpleName()+" order="+(order++)+" class="+p.getClass().getName()+" origin="+origin(p.getClass()));}
  }
 }
 static BufferedImage sample(boolean alpha) {
  BufferedImage image=new BufferedImage(96,80,alpha?BufferedImage.TYPE_INT_ARGB:BufferedImage.TYPE_INT_RGB);
  for(int y=0;y<80;y++)for(int x=0;x<96;x++)image.setRGB(x,y,((alpha?(x<16?0:160):255)<<24)|((x*2+12)<<16)|((y*2+20)<<8)|90);
  return image;
 }
 static ImageWriter writer(String format,boolean own) {
  Iterator<ImageWriter> i=ImageIO.getImageWritersByFormatName(format);
  while(i.hasNext()){ImageWriter w=i.next();if(!own || w.getClass().getName().startsWith("com.sun.media.imageioimpl."))return w;w.dispose();}
  throw new AssertionError("no writer "+format+" own="+own);
 }
 static void roundtrip(Path output,String format,boolean own,boolean geotiff)throws Exception {
  boolean alpha=format.equals("PNG");BufferedImage input=sample(alpha);ImageWriter w=writer(format,own);Path file=output.resolve(format+"-"+(own?"selected":"automatic")+(geotiff?"-geo":"")+".img");
  String wc=w.getClass().getName();ImageWriteParam param=w.getDefaultWriteParam();IIOMetadata metadata=w.getDefaultImageMetadata(new ImageTypeSpecifier(input),param);
  if(format.equals("JPEG")){param.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);param.setCompressionQuality(0.95f);}
  if(geotiff){TIFFDirectory d=TIFFDirectory.createFromMetadata(metadata);GeoTIFFTagSet ts=GeoTIFFTagSet.getInstance();d.addTagSet(ts);d.addTIFFField(new TIFFField(ts.getTag(33550),TIFFTag.TIFF_DOUBLE,3,new double[]{0.25,0.25,0}));d.addTIFFField(new TIFFField(ts.getTag(33922),TIFFTag.TIFF_DOUBLE,6,new double[]{0,0,0,12,48,0}));d.addTIFFField(new TIFFField(ts.getTag(34735),TIFFTag.TIFF_SHORT,12,new char[]{1,1,0,2,1024,0,1,2,2048,0,1,4326}));metadata=d.getAsMetadata();}
  try(ImageOutputStream stream=ImageIO.createImageOutputStream(file.toFile())) {w.setOutput(stream);w.write(null,new IIOImage(input,null,metadata),param);}finally{w.dispose();}
  try(ImageInputStream stream=ImageIO.createImageInputStream(file.toFile())) {
   Iterator<ImageReader> readers=ImageIO.getImageReaders(stream);if(!readers.hasNext())throw new AssertionError("no reader "+format);
   ImageReader r=readers.next();if(own){r.dispose(); r = new com.sun.media.imageioimpl.plugins.tiff.TIFFImageReaderSpi().createReaderInstance();}
   try {r.setInput(stream);BufferedImage result=r.read(0);if(result.getWidth()!=96||result.getHeight()!=80)throw new AssertionError("dimensions");long delta=0;int max=0;
    for(int y=0;y<80;y++)for(int x=0;x<96;x++){int a=input.getRGB(x,y),b=result.getRGB(x,y);for(int shift=0;shift<24;shift+=8){int diff=Math.abs(((a>>>shift)&255)-((b>>>shift)&255));delta+=diff;max=Math.max(max,diff);}if(alpha&&(a>>>24)!=(b>>>24))throw new AssertionError("alpha changed");}
    double mean=delta/(96.0*80*3);if(format.equals("JPEG")){if(mean>3||max>12)throw new AssertionError("JPEG error mean="+mean+" max="+max);}else if(delta!=0)throw new AssertionError(format+" pixel loss "+delta+" input="+input.getColorModel()+" output="+result.getColorModel()+" rgb="+Integer.toHexString(input.getRGB(48,40))+"/"+Integer.toHexString(result.getRGB(48,40))+" raster="+Arrays.toString(input.getRaster().getPixel(48,40,(int[])null))+"/"+Arrays.toString(result.getRaster().getPixel(48,40,(int[])null)));
    if(geotiff){TIFFDirectory d=TIFFDirectory.createFromMetadata(r.getImageMetadata(0));if(d.getTIFFField(33550).getAsDouble(0)!=0.25||d.getTIFFField(33922).getAsDouble(4)!=48||d.getTIFFField(34735).getAsInt(11)!=4326)throw new AssertionError("GeoTIFF tags lost");}
    System.out.println("roundtrip format="+format+" geotiff="+geotiff+" own="+own+" writer="+wc+" reader="+r.getClass().getName()+" reader_origin="+origin(r.getClass())+" mean_error="+mean+" max_error="+max+" file_sha256="+HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file))));
   }finally{r.dispose();}
  }
 }
 static void fax(Path output,String compression)throws Exception {
  BufferedImage input=new BufferedImage(97,81,BufferedImage.TYPE_BYTE_BINARY);
  for(int y=0;y<81;y++)for(int x=0;x<97;x++)input.getRaster().setSample(x,y,0,((x/7)+(y/5))%2);
  ImageWriter w=new com.sun.media.imageioimpl.plugins.tiff.TIFFImageWriterSpi().createWriterInstance();ImageWriteParam p=w.getDefaultWriteParam();p.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);p.setCompressionType(compression);Path file=output.resolve(compression.replace(' ','_')+".tif");
  try(ImageOutputStream stream=ImageIO.createImageOutputStream(file.toFile())){w.setOutput(stream);w.write(null,new IIOImage(input,null,null),p);}finally{w.dispose();}
  ImageReader r=new com.sun.media.imageioimpl.plugins.tiff.TIFFImageReaderSpi().createReaderInstance();
  try(ImageInputStream stream=ImageIO.createImageInputStream(file.toFile())){r.setInput(stream);BufferedImage decoded=r.read(0);for(int y=0;y<81;y++)for(int x=0;x<97;x++)if(input.getRGB(x,y)!=decoded.getRGB(x,y))throw new AssertionError("fax pixel "+compression+" "+x+","+y);}finally{r.dispose();}
  System.out.println("tiff_java_fax compression="+compression+" dimensions=97x81 exact_pixels=true");
 }
 public static void main(String[]args)throws Exception {
  if(System.getProperty("ambisgis.witness.renderer")!=null)RenderingWitness.main(new String[]{System.getProperty("ambisgis.witness.renderer"),System.getProperty("ambisgis.witness.renderer.sha256")});
Path out=Path.of(args[0]);Files.createDirectories(out);ImageIO.setUseCache(false);inventory();for(String f:new String[]{"PNG","JPEG","TIFF"})roundtrip(out,f,false,false);roundtrip(out,"TIFF",true,true);for(String c:new String[]{"CCITT RLE","CCITT T.4","CCITT T.6"})fax(out,c);System.out.println("NOJPEG2000_IMAGEIO_POSITIVE_PASS");}
}
