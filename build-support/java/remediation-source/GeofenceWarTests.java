import java.lang.reflect.Field;
import java.sql.Connection;
import java.util.*;
import javax.sql.DataSource;
import org.junit.runner.JUnitCore;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;
import org.springframework.context.support.ClassPathXmlApplicationContext;
import org.springframework.aop.framework.Advised;
import org.springframework.aop.support.AopUtils;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;
import org.geoserver.geofence.core.dao.GFUserDAO;
import org.geoserver.geofence.core.model.GFUser;

public class GeofenceWarTests {
 public static void main(String[] args)throws Exception {
  String lib=new java.io.File(args[0]).getCanonicalPath()+java.io.File.separator;
  for(String name:new String[]{"org.geoserver.geofence.core.dao.impl.GFUserDAOImpl","org.geoserver.geofence.core.model.GFUser","org.aspectj.lang.JoinPoint","org.aspectj.weaver.tools.PointcutParser","org.springframework.transaction.interceptor.TransactionInterceptor","org.hibernate.Session","org.postgresql.Driver"}){
   Class<?> c=Class.forName(name);String from=new java.io.File(c.getProtectionDomain().getCodeSource().getLocation().toURI()).getCanonicalPath();
   if(!from.startsWith(lib))throw new AssertionError("production class escaped WAR: "+name+" "+from);
   System.out.println("production-origin="+name+" "+from);
  }
  Class<?>[] tests=new Class<?>[args.length-1];for(int i=1;i<args.length;i++)tests[i-1]=Class.forName(args[i]);
  ClassPathXmlApplicationContext ctx=null;
  try {
   Result result=new JUnitCore().run(tests);for(Failure f:result.getFailures())System.out.println(f.getTrace());
   System.out.println("native-dao-tests="+result.getRunCount()+" failures="+result.getFailureCount()+" skipped="+result.getIgnoreCount());
   Field field=Class.forName("org.geoserver.geofence.core.dao.BaseDAOTest").getDeclaredField("ctx");field.setAccessible(true);ctx=(ClassPathXmlApplicationContext)field.get(null);
   if(!result.wasSuccessful()||result.getRunCount()==0||ctx==null)throw new AssertionError("native DAO tests failed");
   final GFUserDAO dao=(GFUserDAO)ctx.getBean("gfUserDAO");
   if(!AopUtils.isAopProxy(dao)||!(dao instanceof Advised))throw new AssertionError("real DAO transaction proxy missing");
   boolean txAdvice=false;for(org.springframework.aop.Advisor advisor:((Advised)dao).getAdvisors())if(advisor.getAdvice() instanceof org.springframework.transaction.interceptor.TransactionInterceptor)txAdvice=true;
   if(!txAdvice)throw new AssertionError("transaction advice missing");
   DataSource ds=(DataSource)ctx.getBean("geofenceDataSource");try(Connection c=ds.getConnection()){
    if(!c.getMetaData().getDatabaseProductName().equals("PostgreSQL"))throw new AssertionError("real PostgreSQL required");
    System.out.println("database-product="+c.getMetaData().getDatabaseProductName());
   }
   TransactionTemplate tx=new TransactionTemplate((PlatformTransactionManager)ctx.getBean("geofenceTransactionManager"));
   Long rolled=tx.execute(new TransactionCallback<Long>(){public Long doInTransaction(TransactionStatus status){GFUser u=new GFUser();u.setName("ambisgis_rollback_witness");dao.persist(u);status.setRollbackOnly();return u.getId();}});
   if(dao.find(rolled)!=null)throw new AssertionError("rollback persisted row");
   Long committed=tx.execute(new TransactionCallback<Long>(){public Long doInTransaction(TransactionStatus status){GFUser u=new GFUser();u.setName("ambisgis_commit_witness");dao.persist(u);return u.getId();}});
   if(dao.find(committed)==null)throw new AssertionError("commit lost row");dao.removeById(committed);if(dao.find(committed)!=null)throw new AssertionError("cleanup lost");
   System.out.println("real-geofence-proxy-commit-rollback=passed");
  } finally {if(ctx!=null)ctx.close();}
 }
}
