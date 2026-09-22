import java.lang.reflect.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
/** Compare effective public contracts, including inherited abstract methods. */
public class AspectJApi {
 static URLClassLoader loader(String cp)throws Exception {
  String[] files=cp.split(java.io.File.pathSeparator);URL[] urls=new URL[files.length];
  for(int i=0;i<files.length;i++)urls[i]=Paths.get(files[i]).toUri().toURL();
  return new URLClassLoader(urls,ClassLoader.getSystemClassLoader().getParent());
 }
 static String signature(Method m){return m.getName()+Arrays.toString(m.getParameterTypes())+":"+m.getReturnType().getName()+":"+Modifier.isStatic(m.getModifiers());}
 public static void main(String[] args)throws Exception {
  URLClassLoader before=loader(args[1]),after=loader(args[2]);int classes=0,methods=0,fields=0;List<String> errors=new ArrayList<String>();
  try(JarFile jar=new JarFile(args[0])) {
   Enumeration<JarEntry> entries=jar.entries();
   while(entries.hasMoreElements()){
    String path=entries.nextElement().getName();
    if(!path.endsWith(".class")||path.contains("$")||path.startsWith("com/bea/")||path.contains("JRockitAgent"))continue;
    String name=path.substring(0,path.length()-6).replace('/','.');
    Class<?> b=Class.forName(name,false,before),a=Class.forName(name,false,after);
    if(!Modifier.isPublic(b.getModifiers()))continue;classes++;
    Set<String> available=new HashSet<String>();for(Method m:a.getMethods())available.add(signature(m));
    for(Method m:b.getMethods()){methods++;if(!available.contains(signature(m)))errors.add(name+" "+signature(m));}
    Set<String> afields=new HashSet<String>();for(Field f:a.getFields())afields.add(f.getName()+":"+f.getType().getName()+":"+Modifier.isStatic(f.getModifiers()));
    for(Field f:b.getFields()){fields++;if(!afields.contains(f.getName()+":"+f.getType().getName()+":"+Modifier.isStatic(f.getModifiers())))errors.add(name+" field "+f.getName());}
   }
  }
  if(!errors.isEmpty())throw new AssertionError(errors.toString());
  System.out.println("effective-public-api=passed; classes="+classes+"; methods="+methods+"; fields="+fields);
 }
}
