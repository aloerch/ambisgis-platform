// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
import junit.framework.*;
/** Execute unmodified donor test methods for the selected non-function writer contract. */
public class NativeSelection {
    public static void main(String[] args)throws Exception{
        TestSuite suite=new TestSuite();
        for(String name:new String[]{"net.sf.json.util.TestJSONBuilder","net.sf.json.util.TestJSONStringer"})
            for(String method:new String[]{"testCreateArray","testCreateEmptyArray","testCreateEmptyArrayWithNullObjects","testCreateEmptyObject"})
                suite.addTest((Test)Class.forName(name).getConstructor(String.class).newInstance(method));
        TestResult result=junit.textui.TestRunner.run(suite);
        if(!result.wasSuccessful())throw new AssertionError("Selected native failures");
        System.out.println("unchanged-native-selected="+result.runCount());
    }
}
