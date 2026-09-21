package remediation.weaving;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
@Aspect public class WitnessAspect {
 public static int calls;
 @Before("execution(* remediation.weaving.Target.compute(..))") public void count() {calls++;}
}
