package remediation.weaving;
public class Main {public static void main(String[] args) {
 if(new Target().compute(21)!=42 || WitnessAspect.calls!=1)throw new AssertionError("load-time advice did not execute");
 System.out.println("actual-load-time-weaving=passed; advice calls="+WitnessAspect.calls);
}}
