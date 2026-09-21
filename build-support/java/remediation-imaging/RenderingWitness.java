import java.awt.*;
import java.awt.geom.*;
import java.awt.image.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import sun.java2d.pipe.RenderingEngine;
public class RenderingWitness {
 static byte[] draw() throws Exception {
  BufferedImage image=new BufferedImage(160,120,BufferedImage.TYPE_INT_ARGB);
  Graphics2D g=image.createGraphics();
  try { g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);
   g.setColor(new Color(210,40,70,180));g.fill(new Ellipse2D.Double(17.25,15.5,88.5,72.75));
   g.setStroke(new BasicStroke(9f,BasicStroke.CAP_ROUND,BasicStroke.JOIN_MITER));
   g.setColor(new Color(15,40,230,220));Path2D p=new Path2D.Double();p.moveTo(10.3,102.4);p.lineTo(60.5,24.3);p.lineTo(144.7,106.1);g.draw(p);
  } finally {g.dispose();}
  int transparent=0,partial=0,opaque=0;MessageDigest d=MessageDigest.getInstance("SHA-256");
  for(int y=0;y<120;y++)for(int x=0;x<160;x++){int pixel=image.getRGB(x,y),alpha=pixel>>>24;if(alpha==0)transparent++;else if(alpha<255)partial++;else opaque++;for(int s=0;s<32;s+=8)d.update((byte)(pixel>>>s));}
  if(transparent<5000 || partial<5000 || image.getRGB(0,0)!=0 || (image.getRGB(40,60)>>>24)==0)throw new AssertionError("geometry/transparency/antialiasing witness");
  return d.digest();
 }
 public static void main(String[] args)throws Exception {
  String name=RenderingEngine.getInstance().getClass().getName();
  if(!name.equals("sun.java2d.marlin.DMarlinRenderingEngine"))throw new AssertionError("unexpected renderer "+name);
  Class<?> engine=RenderingEngine.getInstance().getClass();String origin=engine.getResource("DMarlinRenderingEngine.class").toString();
  if(!origin.startsWith("jar:"+Path.of(args[0]).toUri().toString()+"!/") && !origin.equals("jar:file:"+Path.of(args[0]).toString()+"!/sun/java2d/marlin/DMarlinRenderingEngine.class"))throw new AssertionError("renderer did not originate in selected variant: "+origin);
  String version=(String)Class.forName("sun.java2d.marlin.Version").getMethod("getVersion").invoke(null);
  try(java.util.jar.JarFile selected=new java.util.jar.JarFile(args[0])) { String declared=selected.getManifest().getMainAttributes().getValue("Implementation-Version"); if(!version.equals(declared)||!version.startsWith("ambisgis-marlin-0.9.4.8-headless-temurin17-"))throw new AssertionError(version); }
  String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[0]))));if(!hash.equals(args[1]))throw new AssertionError("jar hash");
  byte[] expected=draw();ExecutorService workers=Executors.newFixedThreadPool(8);try {ArrayList<Future<byte[]>> fs=new ArrayList<>();for(int i=0;i<128;i++)fs.add(workers.submit(RenderingWitness::draw));for(Future<byte[]> f:fs)if(!Arrays.equals(expected,f.get()))throw new AssertionError("nondeterministic concurrent renderer");}finally{workers.shutdownNow();if(!workers.awaitTermination(5,TimeUnit.SECONDS))throw new AssertionError("workers leaked");}
  System.out.println("renderer="+name+" origin="+origin+" version="+version+" tasks=128 threads=8 pixel_sha256="+HexFormat.of().formatHex(expected));
 }
}
